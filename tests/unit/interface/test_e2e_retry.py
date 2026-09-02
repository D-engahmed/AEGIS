"""End-to-end retry/backoff: real REST 429 target through the worker.

Verifies the production retry contract over the real HTTP path: a transient
(rate-limit) target is retried only up to `max_attempts` with backoff, earlier
successful executions keep their partial evidence, the failing execution is
recorded with a distinguishable failure code, and the run is FAILED
(failure-architecture.md, async-execution-contract.md).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.application.evaluation import EvaluationService
from aegis.application.runner import EvaluationRunner
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.failures import FailureCode
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.execution.retry import RetryPolicy
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryEvidenceRepository,
    MemoryExecutionRepository,
    MemoryExperimentRepository,
    MemoryQueue,
    MemoryResultRepository,
    MemoryRunRepository,
)
from aegis.infrastructure.rest_target import RestTargetClient

pytestmark = pytest.mark.unit


class _RetryHandler(BaseHTTPRequestHandler):
    """Returns 200 for 'ok' inputs and 429 for 'rate'; records every hit."""

    protocol_version = "HTTP/1.1"
    hits: list[str] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))
        input_value = str(request.get("input", ""))
        _RetryHandler.hits.append(input_value)
        if input_value == "rate":
            self.send_error(429, "too many requests")
            return
        body = json.dumps(
            {"output": input_value, "latency_ms": 2.0, "trace_artifact_id": "trace/ok"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def retry_base_url() -> str:
    _RetryHandler.hits.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RetryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@dataclass
class _RecordedSleep:
    calls: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _build_runner(clock, retry: RetryPolicy, sleep):
    experiments = MemoryExperimentRepository()
    runs = MemoryRunRepository()
    executions = MemoryExecutionRepository()
    results = MemoryResultRepository()
    catalog = InMemoryDataCatalog()

    dataset = create_dataset(clock, "org:1", "prj:1", "retry-qa")
    version, _ = create_dataset_version(clock, dataset, "1.0.0")
    for input_value in ("ok", "rate", "ok2"):
        version, _ = add_test_case(clock, version, input=input_value, expected=input_value)
    locked, _ = lock_dataset_version(clock, version)
    catalog.register_dataset(locked)

    target = create_target(clock, "org:1", "prj:1", "rate-target", TargetType.MODEL_API)
    target_version = create_target_version(
        clock, target, "1.0.0", config={"base_url": "http://127.0.0.1:39999"}
    )
    catalog.register_target(target_version)

    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "retry-eval",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=locked.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )

    runner = EvaluationRunner(
        clock,
        experiments=experiments,
        runs=runs,
        executions=executions,
        results=results,
        catalog=catalog,
        cancellations=InMemoryCancellationRegistry(),
        queue=MemoryQueue(),
        evidence=MemoryEvidenceRepository(),
        gateway=EvaluationService(clock),
        retry=retry,
        sleep=sleep,
    )
    return runner, target_version, locked, experiment, runs, executions, results


def test_e2e_bounded_retry_keeps_partial_evidence(clock, retry_base_url: str) -> None:
    recorded = _RecordedSleep()
    retry = RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter_ratio=0.0)
    runner, target_version, dataset_version, experiment, runs, executions, results = _build_runner(
        clock, retry, recorded
    )

    out = runner.run(
        RestTargetClient(retry_base_url),
        target_version,
        dataset_version,
        experiment,
    )

    run = out.run
    assert run.status.value == "failed"
    assert run.error is not None
    assert run.error.code is FailureCode.PROVIDER_RATE_LIMIT
    assert run.evidence_summary is not None
    assert run.evidence_summary.partial_preserved
    assert run.evidence_summary.completed_executions == 2  # ok (succeeded) + rate (failed)
    assert run.evidence_summary.total_executions == 3

    # "ok" hit once, "rate" bounded to max_attempts=3, "ok2" never reached.
    assert _RetryHandler.hits.count("ok") == 1
    assert _RetryHandler.hits.count("rate") == 3
    assert "ok2" not in _RetryHandler.hits
    # two backoff pauses for the two retries of the failing execution
    assert len(recorded.calls) == 2

    # the succeeded case's score and evidence are preserved despite the failure
    assert {r.metric_name for r in out.results} == {"exact_match"}
    assert len(out.results) == 1
    assert out.results[0].score == 1.0
    assert len(out.evidence) == 1

    failing = [ex for ex in executions.list_for_run(run.id) if ex.status.value == "failed"]
    assert len(failing) == 1
    assert failing[0].retries == 2
    assert failing[0].failure.code is FailureCode.PROVIDER_RATE_LIMIT


def test_e2e_retry_precision_produces_deterministic_backoff(clock, retry_base_url: str) -> None:
    recorded = _RecordedSleep()
    retry = RetryPolicy(max_attempts=4, base_delay_seconds=1.0, jitter_ratio=0.0)
    runner, target_version, dataset_version, experiment, runs, executions, results = _build_runner(
        clock, retry, recorded
    )
    out = runner.run(RestTargetClient(retry_base_url), target_version, dataset_version, experiment)
    assert out.run.status.value == "failed"
    # attempts 1,2,3 each get 1s (capped base); 3 retries for a max_attempts=4 run
    assert len(recorded.calls) == 3
    assert recorded.calls == [1.0, 2.0, 4.0]


__all__ = []
