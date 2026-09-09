"""Gate flow over the persistent slice: Redis + Postgres + threshold gate.

Same shape as the golden flow, but the target never matches the goldens so the
configured threshold gate blocks the run; the report must survive a container
restart, and so must its override.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.domain.tenants import create_organization
from aegis.domain.time import FrozenClock
from aegis.execution.worker import ExecutionWorker
from aegis.infrastructure.rest_target import RestTargetClient
from aegis.interface.container import Container
from aegis.policy.application import ThresholdGate
from aegis.policy.models import RunGateVerdict

pytestmark = pytest.mark.integration


class _MismatchHandler(BaseHTTPRequestHandler):
    """Always responds with an output that can never equal the goldens."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps(
            {"output": "definitely-wrong", "latency_ms": 1.0, "trace_artifact_id": "trace/1"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def target_base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MismatchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC))


@dataclass(frozen=True)
class _Fixture:
    container: Container
    organization: object
    experiment_id: str
    base_url: str


@pytest.fixture
def context(database_url: str, redis_url: str, target_base_url: str, clock: FrozenClock):
    container = Container(
        clock,
        database_url=database_url,
        redis_url=redis_url,
        gates=(ThresholdGate("dim/exact-match", "exact_match", min_value=0.9),),
    )

    dataset = create_dataset(clock, "org:1", "prj:1", "gate-qa")
    dataset_version, _ = create_dataset_version(clock, dataset, "1.0.0")
    for value in ("hello", "world"):
        dataset_version, _ = add_test_case(clock, dataset_version, input=value, expected=value)
    dataset_version, _ = lock_dataset_version(clock, dataset_version)
    container.catalog.register_dataset(dataset_version)

    target = create_target(clock, "org:1", "prj:1", "gate", TargetType.MODEL_API)
    target_version = create_target_version(clock, target, "1.0.0", {"base_url": target_base_url})
    container.catalog.register_target(target_version)

    organization = create_organization(clock, "Acme", "user:alice")[0]
    experiment = container.experiment_service.create(
        organization,
        "user:alice",
        "prj:1",
        "gate-eval",
        ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    return _Fixture(container, organization, experiment.id, target_base_url)


def test_blocking_gate_report_survives_restart(context, clock) -> None:
    run_view = context.container.run_service.submit(
        context.organization, "user:alice", context.experiment_id
    )
    engine = context.container.runner.engine(RestTargetClient(context.base_url))
    ExecutionWorker(engine, context.container.queue).process_next()
    outcome = context.container.runner.finish_run(run_view.run_id)
    assert outcome.run.status.value == "succeeded"
    assert {r.score for r in outcome.results} == {0.0}

    report = context.container.run_gate_store.load(run_view.run_id)
    assert report is not None
    assert report.verdict is RunGateVerdict.BLOCK
    assert report.is_blocked

    restarted = Container(
        clock,
        database_url=context.container.stores.dsn,
        redis_url="redis://127.0.0.1:6380/0",
        gates=(ThresholdGate("dim/exact-match", "exact_match", min_value=0.9),),
    )
    reloaded = restarted.run_gate_store.load(run_view.run_id)
    assert reloaded is not None
    assert reloaded.verdict is RunGateVerdict.BLOCK
    assert any(d.gate_id == "dim/exact-match" for d in reloaded.decisions)

    overridden = restarted.run_gates.override(
        reloaded, overridden_by="owner:alice", reason="reviewed and approved by QA"
    )
    assert not overridden.is_blocked
    assert restarted.run_gate_store.load(run_view.run_id).override.overridden_by == "owner:alice"
