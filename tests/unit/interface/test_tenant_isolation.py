"""Cross-tenant isolation: run-scoped reads and mutations are ownership-checked.

Regression guard for the Phase-1 (multi-tenancy) fix: every endpoint that
resolves a run by id must prove the run belongs to the caller's organization
BEFORE returning data or mutating state. A mismatched tenant receives the same
404 as a run that does not exist, so a foreign run id never leaks existence.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from aegis.domain import (
    Experiment,
    ExperimentSnapshot,
    ExperimentStatus,
    MetricResult,
)
from aegis.domain.datasets import DatasetVersion
from aegis.domain.datasets import TestCase as AegisTestCase
from aegis.domain.execution import ExecutionRecord, run_created
from aegis.domain.results import EvidenceReference
from aegis.domain.targets import TargetVersion
from aegis.domain.tenants import Role
from aegis.evidence.build import link_evidence_to_score
from aegis.interface.app import create_app
from aegis.interface.container import Container
from tests.conftest import SteppingClock

pytestmark = pytest.mark.unit


@pytest.fixture
def api():
    container = Container(clock=SteppingClock(timedelta(seconds=1)))
    client = TestClient(create_app(container))
    yield container, client


def _headers(container: Container, org: str = "org:1", role: Role = Role.OWNER) -> dict[str, str]:
    token = container.auth.issue("alice" if org == "org:1" else "eve", org, role)
    return {"Authorization": f"Bearer {token}"}


def _seed_org1_run(container: Container) -> tuple[str, str]:
    """Create an org:1 run with a published result and linked evidence.

    Returns (run_id, metric_result_id).
    """
    clock = container.clock
    experiment = Experiment(
        id="exp:1",
        organization_id="org:1",
        project_id="prj:1",
        name="golden",
        snapshot=ExperimentSnapshot(
            target_version_id="tvr:1",
            dataset_version_id="dsv:1",
        ),
        created_at=clock.now(),
        status=ExperimentStatus.RUNNING,
    )
    run = run_created(
        clock,
        organization_id="org:1",
        project_id="prj:1",
        experiment_id="exp:1",
        snapshot=experiment.snapshot,
        created_by="alice",
    )
    container.runs.save(run)
    run_id = run.id

    target_version = TargetVersion(
        id="tvr:1",
        target_id="tgt:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        config={},
        commit_sha="abc",
        created_at=clock.now(),
    )
    dataset_version = DatasetVersion(
        id="dsv:1",
        dataset_id="ds:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        test_cases=(
            AegisTestCase(id="tc:1", dataset_version_id="dsv:1", index=0, input="x", expected="y"),
        ),
    )
    execution = ExecutionRecord(
        id="exe:1",
        run_id=run_id,
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=clock.now(),
    )
    result = MetricResult(
        id="mtr:1",
        run_id=run_id,
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=1.0,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0",
        created_at=clock.now(),
        evidence=(
            EvidenceReference(
                execution_id="exe:1",
                dataset_case_id="tc:1",
                trace_artifact_id="trace/1",
            ),
        ),
    )
    container.results.persist([result])
    link_evidence_to_score(
        container.evidence_repository,
        clock,
        result,
        execution,
        experiment,
        target_version,
        dataset_version,
    )
    return run_id, result.id


def test_run_scoped_reads_reject_foreign_tenant(api) -> None:
    container, client = api
    headers = _headers(container)
    other = _headers(container, "org:2")
    run_id, metric_result_id = _seed_org1_run(container)
    evidence_id = client.get(f"/evidence/runs/{run_id}", headers=headers).json()[0]["id"]

    cases = [
        ("/runs/status", "GET", f"/runs/{run_id}", None),
        ("/runs/results", "GET", f"/runs/{run_id}/results", None),
        ("/evidence/runs", "GET", f"/evidence/runs/{run_id}", None),
        ("/evidence/provenance", "GET", f"/evidence/provenance/{metric_result_id}", None),
        ("/evidence/{id}", "GET", f"/evidence/{evidence_id}", None),
        ("/analysis/trend", "GET", "/analysis/trend/exact_match", [("run_ids", run_id)]),
        (
            "/analysis/regression",
            "GET",
            "/analysis/regression",
            [("baseline_run_id", run_id), ("current_run_id", run_id)],
        ),
        ("/analysis/failures", "GET", "/analysis/failures", [("run_ids", run_id)]),
        ("/observability/cost", "GET", f"/observability/cost/{run_id}", None),
        ("/observability/traces", "GET", f"/observability/traces/{run_id}", None),
    ]
    for _name, method, url, params in cases:
        params = params or {}
        kwargs = {"params": params} if method == "GET" else {}
        assert client.request(method, url, headers=other, **kwargs).status_code == 404, url
        if url != "/analysis/regression":
            assert client.request(method, url, headers=headers, **kwargs).status_code == 200, url


def test_foreign_tenant_cannot_cancel_or_mutate(api) -> None:
    container, client = api
    headers = _headers(container)
    other = _headers(container, "org:2")
    run_id, _metric_result_id = _seed_org1_run(container)

    cancel_attempt = client.post(f"/runs/{run_id}/cancel", headers=other)
    assert cancel_attempt.status_code == 404

    same_org_cancel = client.post(f"/runs/{run_id}/cancel", headers=headers)
    assert same_org_cancel.status_code == 200
    assert same_org_cancel.json()["status"] == "cancelled"


def test_foreign_tenant_cannot_range_over_compare(api) -> None:
    container, client = api
    headers = _headers(container)
    other = _headers(container, "org:2")
    run_id, _metric_result_id = _seed_org1_run(container)

    resp = client.get(
        "/analysis/compare",
        headers=other,
        params=[("run_ids_a", run_id), ("run_ids_b", run_id)],
    )
    assert resp.status_code == 404

    own = client.get(
        "/analysis/compare",
        headers=headers,
        params=[("run_ids_a", run_id), ("run_ids_b", run_id)],
    )
    assert own.status_code == 200


__all__ = ["api"]
