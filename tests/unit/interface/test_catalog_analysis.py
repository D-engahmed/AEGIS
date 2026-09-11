"""Catalog registration + analysis endpoints: prove the workflow over HTTP.

Covers the endpoints the dashboard depends on: registering targets and
datasets, listing the catalog tenant-scoped, experiment snapshots on the wire,
the global runs list, and the regression / trend / compare / failures analysis
surface computing over persisted containers.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from aegis.domain import MetricResult, Role
from aegis.domain.execution import (
    ExperimentSnapshot,
    run_created,
)
from aegis.domain.results import EvidenceReference
from aegis.interface.app import create_app
from aegis.interface.container import Container
from tests.conftest import SteppingClock

pytestmark = pytest.mark.unit


@pytest.fixture
def api():
    container = Container(clock=SteppingClock(timedelta(seconds=1)))
    client = TestClient(create_app(container))
    yield container, client


def _admin_headers(container: Container, org: str = "org:1") -> dict[str, str]:
    token = container.auth.issue("user:alice", org, Role.ADMIN)
    return {"Authorization": f"Bearer {token}"}


def _register_sample(container: Container, client: TestClient, org: str = "org:1") -> None:
    headers = _admin_headers(container, org)
    target = client.post(
        "/catalog/targets",
        headers=headers,
        json={
            "project_id": "prj:1",
            "name": "echo",
            "config": {"base_url": "http://echo:8080", "invoke_path": "/invoke"},
        },
    )
    assert target.status_code == 201, target.text
    dataset = client.post(
        "/catalog/datasets",
        headers=headers,
        json={
            "project_id": "prj:1",
            "name": "qa",
            "test_cases": [{"input": "hello", "expected": "hello"}],
        },
    )
    assert dataset.status_code == 201, dataset.text


def test_catalog_register_and_list(api) -> None:
    container, client = api
    headers = _admin_headers(container)
    _register_sample(container, client)

    body = client.get("/catalog", headers=headers).json()
    assert body["targets"][0]["name"] == "echo"
    assert body["targets"][0]["target_type"] == "llm_application"
    assert body["datasets"][0]["name"] == "qa"
    assert body["datasets"][0]["test_case_count"] == 1
    assert body["datasets"][0]["status"] == "draft"


def test_catalog_is_tenant_scoped(api) -> None:
    container, client = api
    _register_sample(container, client, org="org:1")

    other = _admin_headers(container, "org:2")
    body = client.get("/catalog", headers=other).json()
    assert body == {"targets": [], "datasets": []}


def test_register_target_rejects_non_mapping_config(api) -> None:
    container, client = api
    headers = _admin_headers(container)
    resp = client.post(
        "/catalog/targets",
        headers=headers,
        json={"project_id": "prj:1", "name": "bad", "config": [1, 2, 3]},
    )
    assert resp.status_code == 422


def test_experiment_list_includes_snapshot(api) -> None:
    container, client = api
    headers = _admin_headers(container)
    _register_sample(container, client)
    catalog = client.get("/catalog", headers=headers).json()
    target = catalog["targets"][0]["id"]
    dataset = catalog["datasets"][0]["id"]

    created = client.post(
        "/experiments",
        headers=headers,
        json={
            "name": "demo",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": target,
                "dataset_version_id": dataset,
                "evaluator_version_ids": ["aegis/deterministic/exact_match"],
            },
        },
    )
    assert created.status_code == 201, created.text

    listed = client.get("/experiments", headers=headers).json()
    assert listed[0]["snapshot"]["target_version_id"] == target
    assert listed[0]["snapshot"]["dataset_version_id"] == dataset
    assert listed[0]["snapshot"]["evaluator_version_ids"] == ["aegis/deterministic/exact_match"]


def test_global_runs_list_is_newest_first_and_filterable(api) -> None:
    container, client = api
    headers = _admin_headers(container)
    clock = container.clock
    snapshot = ExperimentSnapshot(
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        evaluator_version_ids=("aegis/deterministic/exact_match",),
    )
    for exp in ("exp:1", "exp:2"):
        run = run_created(clock, "org:1", "prj:1", exp, snapshot, created_by="user:alice")
        container.runs.save(run)

    body = client.get("/runs", headers=headers).json()
    assert len(body) == 2
    assert body[0]["experiment_id"] == "exp:2"
    assert body[1]["experiment_id"] == "exp:1"

    filtered = client.get("/runs?experiment_id=exp:1", headers=headers).json()
    assert len(filtered) == 1 and filtered[0]["experiment_id"] == "exp:1"


def _seed_metric_results(container, n: int, *, base: float, delta: float = 0.0) -> None:
    """Persist two runs with per-cause metric results for regression/trend."""
    clock = container.clock
    snapshot = ExperimentSnapshot(
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        evaluator_version_ids=("aegis/deterministic/exact_match",),
    )
    scores = [base + delta + 0.02 * (i % 3) for i in range(n)]
    run = run_created(clock, "org:1", "prj:1", "exp:1", snapshot, created_by="user:alice")
    container.runs.save(run)
    run_id = run.id
    results = [
        MetricResult(
            id=f"{run_id}:mtr:{i}",
            run_id=run_id,
            execution_id=f"{run_id}:exe:{i}",
            test_case_id=f"tc:{i}",
            metric_name="exact_match",
            score=score,
            evaluator_identity="aegis/deterministic/exact_match",
            evaluator_version="1.0",
            created_at=clock.now(),
            evidence=(
                EvidenceReference(
                    execution_id=f"{run_id}:exe:{i}",
                    dataset_case_id=f"tc:{i}",
                    trace_artifact_id=f"trace/{i}",
                ),
            ),
            reason="unknown" if score < base else None,
            severity="critical" if score < base else "info",
        )
        for i, (score) in enumerate(scores)
    ]
    container.results.persist(results)


def test_analysis_endpoints_return_reports(api) -> None:
    container, client = api
    headers = _admin_headers(container)
    _seed_metric_results(container, 12, base=0.9)
    _seed_metric_results(container, 12, base=0.9, delta=-0.2)
    runs = client.get("/runs", headers=headers).json()
    baseline, current = runs[1]["run_id"], runs[0]["run_id"]

    trend = client.get(
        "/analysis/trend/exact_match",
        headers=headers,
        params=[("run_ids", baseline), ("run_ids", current)],
    )
    assert trend.status_code == 200, trend.text
    trend_body = trend.json()
    assert trend_body["metric_name"] == "exact_match"
    assert len(trend_body["data_points"]) == 2
    assert trend_body["overall_trend"] in {"improving", "declining", "stable"}

    regression = client.get(
        "/analysis/regression",
        headers=headers,
        params={"baseline_run_id": baseline, "current_run_id": current},
    )
    assert regression.status_code == 200, regression.text
    report = regression.json()
    assert report["metric_name"] == "exact_match"
    assert report["is_regression"] is True
    assert report["baseline_score"] > report["current_score"]
    assert report["is_statistically_significant"] is True

    comparison = client.get(
        "/analysis/compare",
        headers=headers,
        params=[("run_ids_a", baseline), ("run_ids_b", current)],
    )
    assert comparison.status_code == 200, comparison.text

    failures = client.get(
        "/analysis/failures",
        headers=headers,
        params=[("run_ids", baseline), ("run_ids", current)],
    )
    assert failures.status_code == 200, failures.text
    assert len(failures.json()) >= 1
