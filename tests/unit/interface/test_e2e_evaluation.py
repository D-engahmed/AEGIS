"""End-to-end evaluation: real REST target through the runner to evidence.

Drives the full in-process pipeline with a real localhost HTTP target and the
concrete in-memory stores: load a locked dataset, execute through the worker +
engine + RestTargetClient, and verify metric results with complete evidence
records are persisted ("No score without evidence", evidence-architecture.md).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.infrastructure.rest_target import RestTargetClient
from aegis.interface.container import Container

pytestmark = pytest.mark.unit


@dataclass
class _Call:
    test_case_id: str
    count: int


class _TargetHandler(BaseHTTPRequestHandler):
    """Echoes each test case's golden answer back so exact-match always scores 1.0."""

    protocol_version = "HTTP/1.1"
    calls: list[_Call] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))
        output = str(request.get("input", ""))
        _TargetHandler.calls.append(
            _Call(request.get("test_case_id", ""), len(_TargetHandler.calls) + 1)
        )
        case_id = request.get("test_case_id", "")
        response = json.dumps(
            {
                "output": output,
                "latency_ms": 5.0,
                "input_tokens": 3,
                "output_tokens": 2,
                "cost_usd": 0.001,
                "trace_artifact_id": f"trace/{case_id}",
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def rest_base_url() -> str:
    _TargetHandler.calls.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _register_target(container: Container, base_url: str, label: str = "1.0.0"):
    target = create_target(container.clock, "org:1", "prj:1", "web-target", TargetType.MODEL_API)
    version = create_target_version(
        container.clock,
        target,
        label,
        config={"base_url": base_url, "invoke_path": "/invoke"},
        commit_sha="e2e-sha",
    )
    container.catalog.register_target(version)
    return version


def _register_dataset(container: Container, *cases: tuple[str, str], label: str = "1.0.0"):
    dataset = create_dataset(container.clock, "org:1", "prj:1", "e2e-qa")
    version, _ = create_dataset_version(container.clock, dataset, label)
    for input, expected in cases:
        version, _ = add_test_case(
            container.clock, version, input=input, expected=expected, metadata={"mode": "exact"}
        )
    locked, _ = lock_dataset_version(container.clock, version)
    container.catalog.register_dataset(locked)
    return locked


def test_e2e_deterministic_evaluation_persists_evidence(rest_base_url: str) -> None:
    container = Container()
    target_version = _register_target(container, rest_base_url)
    dataset_version = _register_dataset(
        container,
        ("hello world", "hello world"),
        ("second case", "second case"),
    )

    experiment, _ = create_experiment(
        container.clock,
        "org:1",
        "prj:1",
        "e2e",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    experiment = experiment.start()

    client = RestTargetClient(rest_base_url)
    outcome = container.runner.run(
        client,
        target_version,
        dataset_version,
        experiment,
        evaluator_version_ids=experiment.snapshot.evaluator_version_ids,
    )

    run = outcome.run
    assert run.status.value == "succeeded"
    assert run.evidence_summary.completed_executions == 2
    assert len(_TargetHandler.calls) == 2

    assert {r.score for r in outcome.results} == {1.0}
    assert len(outcome.results) == 2
    for r in outcome.results:
        assert r.evidence and r.evidence[0].trace_artifact_id == f"trace/{r.test_case_id}"

    assert len(outcome.evidence) == 2
    loaded = container.evidence_repository.list_for_run(run.id)
    assert len(loaded) == 2
    assert all(record.classification.value == "internal" for record in loaded)
