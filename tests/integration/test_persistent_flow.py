"""Golden persistent flow: queue + worker + Postgres behind the real app APIs.

A run is submitted through `RunService` (which pushes to Redis), claimed by an
`ExecutionWorker` over the container's engine, executed against a live HTTP
target, and its state must survive a "restart": a brand-new container over the
same database can load the run, results, and evidence.
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

pytestmark = pytest.mark.integration


class _EchoHandler(BaseHTTPRequestHandler):
    """Returns the input untouched, so exact-match always scores 1.0."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        body = json.dumps(
            {
                "output": payload["input"],
                "latency_ms": 1.0,
                "trace_artifact_id": f"trace/{payload['test_case_id']}",
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def target_base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 9, 9, 11, 0, 0, tzinfo=UTC))


@dataclass(frozen=True)
class _Fixture:
    container: Container
    organization: object
    experiment_id: str
    base_url: str


@pytest.fixture
def context(database_url: str, redis_url: str, target_base_url: str, clock: FrozenClock):
    """Fresh schema, catalog entries pinned to the live HTTP target, one experiment."""
    container = Container(
        clock,
        database_url=database_url,
        redis_url=redis_url,
    )

    dataset = create_dataset(clock, "org:1", "prj:1", "echo-qa")
    dataset_version, _ = create_dataset_version(clock, dataset, "1.0.0")
    for value in ("hello", "world"):
        dataset_version, _ = add_test_case(clock, dataset_version, input=value, expected=value)
    dataset_version, _ = lock_dataset_version(clock, dataset_version)
    container.catalog.register_dataset(dataset_version)

    target = create_target(clock, "org:1", "prj:1", "echo", TargetType.MODEL_API)
    target_version = create_target_version(clock, target, "1.0.0", {"base_url": target_base_url})
    container.catalog.register_target(target_version)

    organization = create_organization(clock, "Acme", "user:alice")[0]
    experiment = container.experiment_service.create(
        organization,
        "user:alice",
        "prj:1",
        "echo-eval",
        ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    return _Fixture(container, organization, experiment.id, target_base_url)


def test_persistent_run_survives_restart(context, clock) -> None:
    run_view = context.container.run_service.submit(
        context.organization, "user:alice", context.experiment_id
    )
    assert context.container.queue.pending() == 1

    engine = context.container.runner.engine(RestTargetClient(context.base_url))
    worker = ExecutionWorker(engine, context.container.queue)
    assert worker.process_next() == 1
    assert context.container.queue.pending() == 0
    outcome = context.container.runner.finish_run(run_view.run_id)

    # Status reflects SUCCEEDED with linked evidence through the app API.
    finished = context.container.run_service.status(
        context.organization, "user:alice", run_view.run_id
    )
    assert finished.status == "succeeded"
    assert all(r.score == 1.0 for r in outcome.results)

    # "Restart": a second container over the same database sees everything.
    restarted = Container(
        clock,
        database_url=context.container.stores.dsn,
        redis_url="redis://127.0.0.1:6380/0",
    )
    again = restarted.run_service.status(context.organization, "user:alice", run_view.run_id)
    assert again.status == "succeeded"

    persisted_results = restarted.results.list_for_run(run_view.run_id)
    assert len(persisted_results) == 2
    assert {r.score for r in persisted_results} == {1.0}
    assert len(restarted.evidence_repository.list_for_run(run_view.run_id)) == 2


def test_submit_is_idempotent_across_restart(context, clock) -> None:
    first = context.container.run_service.submit(
        context.organization, "user:alice", context.experiment_id, idempotency_key="key-1"
    )
    engine = context.container.runner.engine(RestTargetClient(context.base_url))
    ExecutionWorker(engine, context.container.queue).process_next()

    # A new container + the same key returns the original run, no duplicate.
    restarted = Container(
        clock,
        database_url=context.container.stores.dsn,
        redis_url="redis://127.0.0.1:6380/0",
    )
    replay = restarted.run_service.submit(
        context.organization, "user:alice", context.experiment_id, idempotency_key="key-1"
    )
    assert replay.run_id == first.run_id
    assert len(restarted.executions.list_for_run(first.run_id)) == 2
