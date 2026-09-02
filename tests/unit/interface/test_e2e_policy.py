"""End-to-end policy gate: a blocking threshold on a real HTTP run.

Verifies the policy gate contract over the full in-process pipeline: a run
completes (SUCCEEDED), a configured ThresholdGate classifies it as BLOCK with a
HIGH/FAIL decision, the gate report is persisted, and an authorized override
records who unblocked it — matching the non-compensatory gate model in
`deployment-strategy.md`.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.application.evaluation import EvaluationService
from aegis.application.run_gates import RunGateService
from aegis.application.runner import EvaluationRunner
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryEvidenceRepository,
    MemoryExecutionRepository,
    MemoryExperimentRepository,
    MemoryQueue,
    MemoryResultRepository,
    MemoryRunGateStore,
    MemoryRunRepository,
)
from aegis.infrastructure.rest_target import RestTargetClient
from aegis.policy.application import ThresholdGate
from aegis.policy.models import GateSeverity, RunGateVerdict, Verdict

pytestmark = pytest.mark.unit


class _BlockedHandler(BaseHTTPRequestHandler):
    """Always returns an output that never matches the golden answer."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        wrong = "not-the-'expected'-value"
        body = json.dumps(
            {"output": wrong, "latency_ms": 2.0, "trace_artifact_id": "trace/gate"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def gate_base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BlockedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@dataclass
class _Harness:
    runner: EvaluationRunner
    target_version: object
    dataset_version: object
    experiment: object
    gate_service: RunGateService
    store: MemoryRunGateStore


def _build(clock) -> _Harness:
    catalog = InMemoryDataCatalog()

    dataset = create_dataset(clock, "org:1", "prj:1", "gate-qa")
    version, _ = create_dataset_version(clock, dataset, "1.0.0")
    for input_value in ("hello", "world"):
        version, _ = add_test_case(clock, version, input=input_value, expected=input_value)
    locked, _ = lock_dataset_version(clock, version)
    catalog.register_dataset(locked)

    target = create_target(clock, "org:1", "prj:1", "gate-target", TargetType.MODEL_API)
    target_version = create_target_version(
        clock,
        target,
        "1.0.0",
        config={"base_url": "http://127.0.0.1:39999"},
    )
    catalog.register_target(target_version)

    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "gate-eval",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=locked.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )

    store = MemoryRunGateStore()
    gate_service = RunGateService(
        store,
        clock,
        gates=(ThresholdGate("dim/exact-match", "exact_match", min_value=0.9),),
    )

    runner = EvaluationRunner(
        clock,
        experiments=MemoryExperimentRepository(),
        runs=MemoryRunRepository(),
        executions=MemoryExecutionRepository(),
        results=MemoryResultRepository(),
        catalog=catalog,
        cancellations=InMemoryCancellationRegistry(),
        queue=MemoryQueue(),
        evidence=MemoryEvidenceRepository(),
        gateway=EvaluationService(clock),
    )
    return _Harness(runner, target_version, locked, experiment, gate_service, store)


def test_e2e_threshold_gate_blocks_run_and_records_report(clock, gate_base_url: str) -> None:
    h = _build(clock)
    out = h.runner.run(
        RestTargetClient(gate_base_url),
        h.target_version,
        h.dataset_version,
        h.experiment,
        run_gates=h.gate_service,
    )

    run = out.run
    assert run.status.value == "succeeded"
    assert {r.score for r in out.results} == {0.0}  # outputs never match goldens

    report = h.store.load(run.id)
    assert report.verdict is RunGateVerdict.BLOCK
    assert report.is_blocked
    blocking = [d for d in report.decisions if d.severity.blocks]
    assert any(d.gate_id == "dim/exact-match" for d in blocking)
    threshold = next(d for d in report.decisions if d.gate_id == "dim/exact-match")
    assert threshold.verdict is Verdict.FAIL
    assert threshold.severity is GateSeverity.HIGH


def test_e2e_gate_override_records_authorization(clock, gate_base_url: str) -> None:
    h = _build(clock)
    out = h.runner.run(
        RestTargetClient(gate_base_url),
        h.target_version,
        h.dataset_version,
        h.experiment,
        run_gates=h.gate_service,
    )

    updated = h.gate_service.override(
        h.store.load(out.run.id),
        overridden_by="owner:alice",
        reason="reviewed and approved by QA",
    )
    assert not updated.is_blocked
    assert updated.override is not None
    assert updated.override.overridden_by == "owner:alice"
    assert updated.override.gate_ids == ("dim/exact-match",)

    persisted = h.store.load(out.run.id)
    assert not persisted.is_blocked
    assert persisted.override.reason == "reviewed and approved by QA"


def test_e2e_gate_override_requires_a_reason(clock, gate_base_url: str) -> None:
    from aegis.domain import ValidationFailed

    h = _build(clock)
    out = h.runner.run(
        RestTargetClient(gate_base_url),
        h.target_version,
        h.dataset_version,
        h.experiment,
        run_gates=h.gate_service,
    )
    with pytest.raises(ValidationFailed):
        h.gate_service.override(h.store.load(out.run.id), overridden_by="alice", reason="   ")


__all__ = []
