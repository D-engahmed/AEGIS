"""SDK contract tests: drive the real AEGIS app through aegis_sdk.

The SDK client is pointed at a test container wrapped in the FastAPI app via an
ASGI transport, so every call exercises the actual authentication, validation,
and persistence path a deployed client would hit.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from aegis.domain import MetricResult, Role
from aegis.domain.execution import ExperimentSnapshot, run_created
from aegis.domain.results import EvidenceReference
from aegis.interface.app import create_app
from aegis.interface.container import Container
from aegis_sdk import (
    AegisClient,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from tests.conftest import SteppingClock

pytestmark = pytest.mark.unit


@pytest.fixture
def sdk() -> tuple[Container, AegisClient]:
    container = Container(clock=SteppingClock(timedelta(seconds=1)))
    app = create_app(container)
    token = container.auth.issue("user:sdk", "org:1", Role.ADMIN)
    with TestClient(app) as test_client:
        client = AegisClient(
            base_url="http://test",
            token=token,
            http=test_client,
        )
        yield container, client
        client.close()


def _register_echo(sdk) -> None:
    container, client = sdk
    target = client.catalog.register_target(
        "prj:1",
        "echo",
        target_type="llm_application",
        config={"base_url": "http://echo:8080", "invoke_path": "/invoke"},
    )
    assert target.name == "echo"
    dataset = client.catalog.register_dataset(
        "prj:1", "qa", test_cases=[{"input": "hello", "expected": "hello"}]
    )
    assert dataset.name == "qa"
    assert dataset.test_case_count == 1
    assert container.audit.query("org:1"), "registration writes must be audited"


def test_full_catalog_and_experiment_workflow(sdk) -> None:
    container, client = sdk
    _register_echo(sdk)

    catalog = client.catalog.all()
    assert len(catalog.targets) == 1 and len(catalog.datasets) == 1
    assert catalog.targets[0].referenced is False

    target_id = catalog.targets[0].id
    dataset_id = catalog.datasets[0].id

    fetched = client.catalog.get_target(target_id)
    assert fetched.name == "echo"
    assert client.catalog.get_dataset(dataset_id).name == "qa"

    experiment = client.experiments.create(
        "prj:1",
        "demo",
        snapshot={
            "target_version_id": target_id,
            "dataset_version_id": dataset_id,
            "evaluator_version_ids": ["aegis/deterministic/exact_match"],
        },
    )
    assert experiment.status == "created"
    assert experiment.snapshot.evaluator_version_ids == ["aegis/deterministic/exact_match"]

    listed = client.experiments.all()
    assert [e.id for e in listed] == [experiment.id]

    started = client.experiments.start(experiment.id)
    assert started.status == "running"

    run = client.runs.submit(experiment.id)
    assert run.experiment_id == experiment.id
    assert not run.terminal

    runs = client.runs.all(experiment_id=experiment.id)
    assert [r.run_id for r in runs] == [run.run_id]
    assert client.runs.all()[0].run_id == run.run_id

    status = client.runs.get(run.run_id)
    assert status.status == "queued"


def test_experiment_runs_are_linked(sdk) -> None:
    container, client = sdk
    _register_echo(sdk)
    catalog = client.catalog.all()
    experiment = client.experiments.create(
        "prj:1",
        "demo",
        snapshot={
            "target_version_id": catalog.targets[0].id,
            "dataset_version_id": catalog.datasets[0].id,
            "evaluator_version_ids": ["aegis/deterministic/exact_match"],
        },
    )
    client.experiments.start(experiment.id)
    run = client.runs.submit(experiment.id)
    linked = client.experiments.runs(experiment.id)
    assert [r.run_id for r in linked] == [run.run_id]


def test_evaluator_discovery_via_sdk(sdk) -> None:
    _, client = sdk
    specs = client.evaluators.all()
    identities = {s.identity for s in specs}
    assert "aegis/deterministic/exact_match" in identities
    assert "aegis/trajectory/recovery" in identities
    by_identity = {s.identity: s for s in specs}
    assert by_identity["aegis/deterministic/exact_match"].requires_trace is False
    assert by_identity["aegis/trajectory/recovery"].requires_trace is True


def _seed_results(container: Container) -> tuple[str, str]:
    """Seed two runs with 12 metric results each (variance > 0 for stats)."""
    clock = container.clock
    snapshot = ExperimentSnapshot(
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        evaluator_version_ids=("aegis/deterministic/exact_match",),
    )
    runs = []
    for base in (0.9, 0.4):
        run = run_created(clock, "org:1", "prj:1", "exp:1", snapshot, created_by="user:sdk")
        container.runs.save(run)
        run_id = run.id
        runs.append(run_id)
        results = [
            MetricResult(
                id=f"{run_id}:mtr:{i}",
                run_id=run_id,
                execution_id=f"{run_id}:exe:{i}",
                test_case_id=f"tc:{i}",
                metric_name="exact_match",
                score=base + 0.02 * (i % 3),
                evaluator_identity="aegis/deterministic/exact_match",
                evaluator_version="1.0",
                created_at=clock.now(),
                evidence=(
                    EvidenceReference(
                        execution_id=f"{run_id}:exe:{i}",
                        dataset_case_id=f"tc:{i}",
                        trace_artifact_id="trace/1",
                    ),
                ),
                reason="unknown" if base < 0.9 else None,
                severity="critical" if base < 0.9 else "info",
            )
            for i in range(12)
        ]
        container.results.persist(results)
    return runs[0], runs[1]


def test_analysis_trend_report_is_typed(sdk) -> None:
    container, client = sdk
    baseline, current = _seed_results(container)

    trend = client.analysis.trend("exact_match", [baseline, current])
    assert trend.metric_name == "exact_match"
    assert len(trend.data_points) == 2
    assert all(p.score is not None for p in trend.data_points)
    assert trend.data_points[0].score > trend.data_points[1].score

    regression = client.analysis.regression(baseline, current)
    assert regression["is_regression"] is True

    failures = client.analysis.failures([baseline, current])
    assert len(failures) >= 1


def test_health_and_security(sdk) -> None:
    _, client = sdk
    health = client.observability.live()
    assert health.overall == "healthy"

    redacted = client.security.redact_pii("call me at 555-012-3456")
    assert "555-012-3456" not in redacted["redacted"]
    assert redacted["pii_spans"]

    token = client.security.issue_token()
    assert token.token

    audit = client.security.audit()
    assert isinstance(audit, list)


def test_error_mapping(sdk) -> None:
    container, client = sdk

    with pytest.raises(NotFoundError):
        client.runs.get("run:nope")

    with pytest.raises(NotFoundError):
        client.policy.verdict("run:nope")

    viewer = AegisClient(
        base_url="http://test",
        token=container.auth.issue("user:viewer", "org:1", Role.VIEWER),
        http=TestClient(create_app(container)),
    )
    try:
        with pytest.raises(AuthorizationError):
            viewer.runs.cancel("run:any")
    finally:
        viewer.close()


def test_validation_error_mapping(sdk) -> None:
    _, client = sdk
    with pytest.raises(ValidationError):
        client.catalog.register_target("prj:1", "bad", config=[1, 2, 3])


def test_conflict_error_mapping(sdk) -> None:
    container, client = sdk
    _register_echo(sdk)
    catalog = client.catalog.all()
    experiment = client.experiments.create(
        "prj:1",
        "demo",
        snapshot={
            "target_version_id": catalog.targets[0].id,
            "dataset_version_id": catalog.datasets[0].id,
            "evaluator_version_ids": ["aegis/deterministic/exact_match"],
        },
    )
    started = client.experiments.start(experiment.id)
    assert started.status == "running"
    with pytest.raises(ConflictError):
        # Starting an already-running experiment must be rejected.
        client.experiments.start(experiment.id)


def test_default_httpx_client_sends_bearer_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(404, json={"detail": "gone"})

    with (
        AegisClient(
            base_url="http://test",
            token="tok:123",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(NotFoundError),
    ):
        client.runs.get("run:x")
    assert seen.get("authorization") == "Bearer tok:123"


def test_run_cancel_awaits_terminal(sdk) -> None:
    container, client = sdk
    _register_echo(sdk)
    catalog = client.catalog.all()
    experiment = client.experiments.create(
        "prj:1",
        "demo",
        snapshot={
            "target_version_id": catalog.targets[0].id,
            "dataset_version_id": catalog.datasets[0].id,
            "evaluator_version_ids": ["aegis/deterministic/exact_match"],
        },
    )
    client.experiments.start(experiment.id)
    run = client.runs.submit(experiment.id)
    cancelled = client.runs.cancel_and_wait(run.run_id)
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_by == "user:sdk"