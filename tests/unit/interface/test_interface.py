"""Interface layer (03): HTTP API behavior over the dependency container."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import fixture

from aegis.domain.tenants import Role
from aegis.interface.container import Container

pytestmark = __import__("pytest").mark.unit


@fixture
def owner_headers(container: Container) -> dict[str, str]:
    token = container.auth.issue("alice", "org:1", Role.OWNER, project_id="prj:1")
    return {"Authorization": f"Bearer {token}"}


@fixture
def non_owner_headers(container: Container) -> dict[str, str]:
    token = container.auth.issue("eve", "org:1", Role.VIEWER, project_id="prj:1")
    return {"Authorization": f"Bearer {token}"}


def test_app_rejects_missing_auth(client: TestClient):
    response = client.get("/security/audit")
    assert response.status_code == 401


def test_app_openapi_serves_schema(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/experiments" in schema["paths"]


def test_health_live(client: TestClient, owner_headers: dict[str, str]):
    response = client.get("/health/live", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == "healthy"


def test_create_and_get_experiment(client: TestClient, owner_headers: dict[str, str]):
    response = client.post(
        "/experiments",
        headers=owner_headers,
        json={
            "name": "golden-qa",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": "tvr:1",
                "dataset_version_id": "dsv:1",
                "evaluator_version_ids": ["aegis/deterministic/exact_match"],
                "settings": {"mode": "exact"},
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "golden-qa"
    assert body["status"] == "created"
    experiment_id = body["id"]

    fetched = client.get(f"/experiments/{experiment_id}", headers=owner_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "golden-qa"


def test_create_experiment_validation_error(client: TestClient, owner_headers: dict[str, str]):
    response = client.post(
        "/experiments",
        headers=owner_headers,
        json={"name": "oops", "project_id": "prj:1", "snapshot": {}},
    )
    assert response.status_code == 422


def test_experiment_not_found(client: TestClient, owner_headers: dict[str, str]):
    response = client.get("/experiments/exp:missing", headers=owner_headers)
    assert response.status_code == 404


def test_viewer_cannot_create_experiment(client: TestClient, non_owner_headers: dict[str, str]):
    response = client.post(
        "/experiments",
        headers=non_owner_headers,
        json={
            "name": "x",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": "tvr:1",
                "dataset_version_id": "dsv:1",
            },
        },
    )
    assert response.status_code == 403


def test_run_submit_and_status(
    client: TestClient, container: Container, owner_headers: dict[str, str]
):
    organization = __import__("aegis.domain", fromlist=["Organization"]).Organization(
        id="org:1",
        name="acme",
        created_at=container.clock.now(),
        members=(
            __import__("aegis.domain.tenants", fromlist=["Membership", "Role"]).Membership(
                "org:1", "alice", __import__("aegis.domain.tenants", fromlist=["Role"]).Role.OWNER
            ),
        ),
    )
    experiment = container.experiment_service.create(
        organization,
        "alice",
        "prj:1",
        "golden",
        __import__("aegis.domain", fromlist=["ExperimentSnapshot"]).ExperimentSnapshot(
            target_version_id="tvr:1",
            dataset_version_id="dsv:1",
            evaluator_version_ids=("aegis/deterministic/exact_match",),
        ),
    )
    container.catalog.register_target(
        __import__("aegis.domain.targets", fromlist=["TargetVersion"]).TargetVersion(
            id="tvr:1",
            target_id="tgt:1",
            organization_id="org:1",
            project_id="prj:1",
            label="1.0.0",
            config={},
            commit_sha="abc",
            created_at=container.clock.now(),
        )
    )
    container.catalog.register_dataset(
        __import__("aegis.domain.datasets", fromlist=["DatasetVersion"]).DatasetVersion(
            id="dsv:1",
            dataset_id="ds:1",
            organization_id="org:1",
            project_id="prj:1",
            label="1.0.0",
        )
    )
    response = client.post(
        "/runs",
        headers=owner_headers,
        json={"experiment_id": experiment.id, "idempotency_key": "k:1"},
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    assert response.json()["status"] == "queued"

    status = client.get(f"/runs/{run_id}", headers=owner_headers)
    assert status.status_code == 200
    assert status.json()["experiment_id"] == experiment.id


def test_run_submit_requires_registered_catalog_versions(
    client: TestClient, owner_headers: dict[str, str]
):
    # experiment created against unregistered versions -> submit should fail 404
    response = client.post(
        "/experiments",
        headers=owner_headers,
        json={
            "name": "golden",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": "tvr:missing",
                "dataset_version_id": "dsv:missing",
            },
        },
    )
    experiment_id = response.json()["id"]
    run = client.post(
        "/runs",
        headers=owner_headers,
        json={"experiment_id": experiment_id},
    )
    assert run.status_code == 404


def test_pii_redaction_endpoint(client: TestClient, owner_headers: dict[str, str]):
    response = client.post(
        "/security/pii/redact",
        headers=owner_headers,
        json={"text": "reach bob@example.com now"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "bob@example.com" not in body["redacted"]
    assert body["pii_spans"][0]["pii_type"] == "email"


def test_token_issuance_endpoint(client: TestClient, owner_headers: dict[str, str]):
    response = client.post("/security/tokens", headers=owner_headers)
    assert response.status_code == 201
    token = response.json()["token"]
    assert token.startswith("aegis.v1.")
    assert response.json()["authentication_method"] == "service_account"


def test_audit_trail_records_actions(client: TestClient, owner_headers: dict[str, str]):
    client.post(
        "/experiments",
        headers=owner_headers,
        json={
            "name": "audited",
            "project_id": "prj:1",
            "snapshot": {
                "target_version_id": "tvr:1",
                "dataset_version_id": "dsv:1",
            },
        },
    )
    entries = client.get("/security/audit", headers=owner_headers)
    assert entries.status_code == 200
    actions = {e["action"] for e in entries.json()}
    assert "experiment.created" in actions


def test_evidence_endpoints(
    client: TestClient, container: Container, owner_headers: dict[str, str]
):
    # seed an evidence record directly into the container
    from aegis.domain import Experiment, ExperimentSnapshot, ExperimentStatus, MetricResult
    from aegis.domain.results import EvidenceReference

    experiment = Experiment(
        id="exp:1",
        organization_id="org:1",
        project_id="prj:1",
        name="golden",
        snapshot=ExperimentSnapshot(
            target_version_id="tvr:1",
            dataset_version_id="dsv:1",
        ),
        created_at=container.clock.now(),
        status=ExperimentStatus.CREATED,
    )
    result = MetricResult(
        id="mtr:1",
        run_id="run:1",
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=1.0,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0",
        created_at=container.clock.now(),
        evidence=(
            EvidenceReference(
                execution_id="exe:1",
                dataset_case_id="tc:1",
                trace_artifact_id="trace/1",
            ),
        ),
    )
    from aegis.domain import TargetVersion
    from aegis.domain.datasets import (
        DatasetVersion,
    )
    from aegis.domain.datasets import (
        TestCase as AegisTestCase,
    )
    from aegis.evidence.build import link_evidence_to_score

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
    target_version = TargetVersion(
        id="tvr:1",
        target_id="tgt:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        config={},
        commit_sha="abc",
        created_at=container.clock.now(),
    )
    execution = __import__("aegis.domain", fromlist=["ExecutionRecord"]).ExecutionRecord(
        id="exe:1",
        run_id="run:1",
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=container.clock.now(),
    )
    link_evidence_to_score(
        container.evidence_repository,
        container.clock,
        result,
        execution,
        experiment,
        target_version,
        dataset_version,
    )

    records = client.get("/evidence/runs/run:1", headers=owner_headers)
    assert records.status_code == 200
    assert len(records.json()) == 1

    provenance = client.get("/evidence/provenance/mtr:1", headers=owner_headers)
    assert provenance.status_code == 200
    assert provenance.json()["experiment_id"] == "exp:1"

    record_id = records.json()[0]["id"]
    single = client.get(f"/evidence/{record_id}", headers=owner_headers)
    assert single.status_code == 200


def test_health_requires_auth(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 401


def _seed_blocked_report(container: Container, run_id: str = "run:gate1") -> None:
    from aegis.policy.models import (
        GateDecision,
        GateSeverity,
        RunGateReport,
        RunGateVerdict,
        Verdict,
    )

    report = RunGateReport(
        run_id=run_id,
        verdict=RunGateVerdict.BLOCK,
        decisions=(
            GateDecision(
                "policy/evidence-gate",
                Verdict.FAIL,
                "missing evidence",
                GateSeverity.HIGH,
            ),
        ),
        evaluated_at=container.clock.now(),
    )
    container.run_gate_store.save(report)


def test_policy_verdict_endpoint(client: TestClient, owner_headers, container: Container):
    _seed_blocked_report(container)
    response = client.get("/policy/verdict/run:gate1", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "block"
    assert body["overridden"] is False
    assert [d["gate_id"] for d in body["decisions"]] == ["policy/evidence-gate"]


def test_policy_verdict_missing(client: TestClient, owner_headers):
    response = client.get("/policy/verdict/run:nope", headers=owner_headers)
    assert response.status_code == 404


def test_policy_override_clears_block(client: TestClient, owner_headers, container: Container):
    _seed_blocked_report(container)
    response = client.post(
        "/policy/verdict/run:gate1/override",
        headers=owner_headers,
        json={"reason": "approved by review board"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overridden"] is True
    assert body["override"]["overridden_by"] == "alice"
    assert body["override"]["reason"] == "approved by review board"

    audit = client.get("/security/audit", headers=owner_headers)
    assert any(entry["action"] == "gate.overridden" for entry in audit.json())


def test_policy_override_refuses_unblocked(client: TestClient, owner_headers, container: Container):
    from aegis.policy.models import (
        GateDecision,
        GateSeverity,
        RunGateReport,
        RunGateVerdict,
        Verdict,
    )

    report = RunGateReport(
        run_id="run:ok",
        verdict=RunGateVerdict.PASS,
        decisions=(GateDecision("policy/evidence-gate", Verdict.PASS, "ok", GateSeverity.INFO),),
        evaluated_at=container.clock.now(),
    )
    container.run_gate_store.save(report)
    response = client.post(
        "/policy/verdict/run:ok/override",
        headers=owner_headers,
        json={"reason": "why"},
    )
    assert response.status_code == 409


def test_policy_override_forbidden_for_viewer(
    client: TestClient, non_owner_headers, container: Container
):
    _seed_blocked_report(container)
    response = client.post(
        "/policy/verdict/run:gate1/override",
        headers=non_owner_headers,
        json={"reason": "force"},
    )
    assert response.status_code == 403


def test_policy_requires_auth(client: TestClient):
    response = client.get("/policy/verdict/run:gate1")
    assert response.status_code == 401


def test_observability_trace_endpoint(client: TestClient, owner_headers, container: Container):
    tracer = container.evaluation_tracers.get_tracer("test")
    tracer.start_span("target.invoke").end("ok")
    tracer.flush("run:trace1")

    response = client.get("/observability/traces/run:trace1", headers=owner_headers)
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    spans = records[0]["spans"]
    assert spans
    assert spans[0]["name"] == "target.invoke"
    assert records[0]["run_id"] == "run:trace1"


__all__ = []
