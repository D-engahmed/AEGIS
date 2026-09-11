"""FastAPI surface tests: Swagger docs, auth, and an authenticated REST flow.

Covers `aegis.interface.app`: the OpenAPI document and Swagger UI are served,
protected routes reject anonymous calls, and an authenticated ADMIN can create
an experiment, start it, submit a run, and read back its status through the
HTTP contract — the flow the front end and Swagger exercise.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aegis.domain import Role
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.interface.app import create_app
from aegis.interface.container import Container

pytestmark = pytest.mark.unit


@pytest.fixture
def api():
    container = Container()
    client = TestClient(create_app(container))
    yield container, client


def _seed(container: Container) -> tuple[str, str]:
    """Register a dataset + target so an experiment can reference them."""
    dataset = create_dataset(container.clock, "org:1", "prj:1", "qa")
    version, _ = create_dataset_version(container.clock, dataset, "1.0.0")
    for value in ("hello", "world"):
        version, _ = add_test_case(container.clock, version, input=value, expected=value)
    version, _ = lock_dataset_version(container.clock, version)
    container.catalog.register_dataset(version)

    target = create_target(container.clock, "org:1", "prj:1", "echo", TargetType.MODEL_API)
    target_version = create_target_version(
        container.clock, target, "1.0.0", {"base_url": "http://127.0.0.1:9"}
    )
    container.catalog.register_target(target_version)
    return target_version.id, version.id


def test_openapi_and_swagger_ui_are_served(api) -> None:
    _, client = api
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/experiments" in openapi.json()["paths"]

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]


def test_protected_routes_require_bearer_token(api) -> None:
    _, client = api
    assert client.get("/health/live").status_code == 401
    assert client.get("/runs/run:missing").status_code == 401
    assert client.post("/runs", json={"experiment_id": "exp:x"}).status_code == 401


def test_health_live_with_token(api) -> None:
    container, client = api
    token = container.auth.issue("user:alice", "org:1", Role.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/health/live", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["overall"] == "healthy"


def test_garbage_token_is_rejected(api) -> None:
    _, client = api
    resp = client.get("/health/live", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 403


def test_dashboard_is_served_at_root(api) -> None:
    _, client = api
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AEGIS" in resp.text
    assert "/static/ui/styles.css" in resp.text
    assert "/static/ui/app.js" in resp.text


def test_dashboard_static_assets_are_served(api) -> None:
    _, client = api
    assert client.get("/static/ui/styles.css").status_code == 200
    assert client.get("/static/ui/app.js").status_code == 200


def test_dev_token_disabled_by_default(api) -> None:
    _, client = api
    resp = client.get("/security/dev-token")
    assert resp.status_code == 403


def test_dev_token_mints_valid_token_when_enabled(api, monkeypatch) -> None:
    container, client = api
    monkeypatch.setenv("AEGIS_DEV_LOGIN", "1")
    resp = client.get("/security/dev-token")
    assert resp.status_code == 200
    token = resp.json()["token"]
    context = container.auth.validate_token(token, now=container.clock.now())
    assert context.organization_id == "org:1"


def test_list_experiments_is_tenant_scoped(api) -> None:
    container, client = api
    target_version_id, dataset_version_id = _seed(container)
    token = container.auth.issue("user:alice", "org:1", Role.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/experiments",
        headers=headers,
        json={
            "name": "listed-exp",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": target_version_id,
                "dataset_version_id": dataset_version_id,
                "evaluator_version_ids": ["aegis/deterministic/exact_match"],
            },
        },
    )
    assert created.status_code == 201

    other = container.auth.issue("user:bob", "org:2", Role.ADMIN)
    other_headers = {"Authorization": f"Bearer {other}"}
    assert client.get("/experiments", headers=other_headers).json() == []

    listed = client.get("/experiments", headers=headers).json()
    assert [e["id"] for e in listed] == [created.json()["id"]]


def test_list_runs_for_experiment(api) -> None:
    container, client = api
    target_version_id, dataset_version_id = _seed(container)
    token = container.auth.issue("user:alice", "org:1", Role.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/experiments",
        headers=headers,
        json={
            "name": "runs-exp",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": target_version_id,
                "dataset_version_id": dataset_version_id,
                "evaluator_version_ids": ["aegis/deterministic/exact_match"],
            },
        },
    ).json()
    run = client.post("/runs", headers=headers, json={"experiment_id": created["id"]}).json()

    runs = client.get(f"/experiments/{created['id']}/runs", headers=headers).json()
    assert [r["run_id"] for r in runs] == [run["run_id"]]
    assert runs[0]["status"] in {"queued", "running"}


def test_authenticated_experiment_start_submit_run_flow(api) -> None:
    container, client = api
    target_version_id, dataset_version_id = _seed(container)
    token = container.auth.issue("user:alice", "org:1", Role.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/experiments",
        headers=headers,
        json={
            "name": "api-echo",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": target_version_id,
                "dataset_version_id": dataset_version_id,
                "evaluator_version_ids": ["aegis/deterministic/exact_match"],
            },
        },
    )
    assert created.status_code == 201
    experiment = created.json()
    assert experiment["status"] == "created"

    started = client.post(f"/experiments/{experiment['id']}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    submitted = client.post("/runs", headers=headers, json={"experiment_id": experiment["id"]})
    assert submitted.status_code == 201
    run = submitted.json()
    assert run["status"] in {"queued", "running"}

    fetched = client.get(f"/runs/{run['run_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["run_id"]


__all__ = []
