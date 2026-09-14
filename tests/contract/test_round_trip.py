"""Round-trip contract: every echoed field survives the full wire path.

Registers real catalog versions, runs the experiment lifecycle through the
typed SDK, and asserts the values that come back match what was sent. This
exercises mappers, schemas, and SDK parsing together — the three sides of
the triple mapping from any single change.
"""

from __future__ import annotations

import pytest

from aegis_sdk import NotFoundError

pytestmark = pytest.mark.contract

SNAPSHOT = {
    "target_version_id": "",
    "dataset_version_id": "",
    "evaluator_version_ids": ["aegis/deterministic/exact_match"],
}


def _seed_catalog(client):
    target = client.catalog.register_target(
        "prj:1",
        "contract-target",
        target_type="llm_application",
        label="2.0.0",
        config={"base_url": "http://contract:8080", "invoke_path": "/invoke"},
    )
    dataset = client.catalog.register_dataset(
        "prj:1",
        "contract-qa",
        label="1.0.0",
        test_cases=[
            {"input": "hello", "expected": "hello"},
            {"input": "world", "expected": "world"},
        ],
    )
    return target, dataset


def test_catalog_round_trip_echoes_every_field(api_client) -> None:
    _, client = api_client
    target, dataset = _seed_catalog(client)

    assert target.name == "contract-target"
    assert target.label == "2.0.0"
    assert target.target_type == "llm_application"
    assert target.config == {"base_url": "http://contract:8080", "invoke_path": "/invoke"}
    assert target.project_id == "prj:1"
    assert target.created_at is not None
    assert target.referenced is False

    assert dataset.name == "contract-qa"
    assert dataset.label == "1.0.0"
    assert dataset.test_case_count == 2
    assert dataset.status == "draft"

    fetched_target = client.catalog.get_target(target.id)
    assert fetched_target.id == target.id
    assert fetched_target.name == target.name
    assert fetched_target.config == target.config

    fetched_dataset = client.catalog.get_dataset(dataset.id)
    assert fetched_dataset.id == dataset.id
    assert fetched_dataset.test_case_count == 2

    summary = client.catalog.all()
    assert [t.id for t in summary.targets] == [target.id]
    assert [d.id for d in summary.datasets] == [dataset.id]


def test_experiment_lifecycle_echoes_snapshot_and_status(api_client) -> None:
    _, client = api_client
    target, dataset = _seed_catalog(client)

    experiment = client.experiments.create(
        "prj:1",
        "contract-eval",
        snapshot={
            **SNAPSHOT,
            "target_version_id": target.id,
            "dataset_version_id": dataset.id,
        },
    )
    assert experiment.name == "contract-eval"
    assert experiment.status == "created"
    assert experiment.snapshot.target_version_id == target.id
    assert experiment.snapshot.dataset_version_id == dataset.id
    assert experiment.snapshot.evaluator_version_ids == ["aegis/deterministic/exact_match"]
    assert experiment.created_at is not None

    started = client.experiments.start(experiment.id)
    assert started.id == experiment.id
    assert started.status == "running"

    run = client.runs.submit(experiment.id)
    assert run.experiment_id == experiment.id
    assert not run.terminal
    assert run.created_at is not None

    status = client.runs.get(run.run_id)
    assert status.run_id == run.run_id
    assert status.status == "queued"

    linked = client.experiments.runs(experiment.id)
    assert [r.run_id for r in linked] == [run.run_id]

    results = client.runs.results(run.run_id)
    assert results == []

    with pytest.raises(NotFoundError):
        # No evaluation has run yet, so no gate report exists.
        client.policy.verdict(run.run_id)


def test_discovery_and_observability_surfaces_are_typed(api_client) -> None:
    _, client = api_client
    _seed_catalog(client)
    specs = client.evaluators.all()
    by_identity = {s.identity: s for s in specs}
    assert by_identity["aegis/deterministic/exact_match"].requires_trace is False
    assert by_identity["aegis/trajectory/recovery"].requires_trace is True
    assert all(s.version and s.display_name and s.metrics for s in specs)

    health = client.observability.live()
    assert health.overall == "healthy"
    assert {c.name for c in health.checks} >= {"api"}

    token = client.security.issue_token()
    assert token.token
    assert token.authentication_method == "service_account"
    assert token.expires_at is not None

    redacted = client.security.redact_pii("call me at 555-012-3456")
    assert set(redacted) == {"redacted", "pii_spans"}
    assert "555-012-3456" not in redacted["redacted"]
    assert redacted["pii_spans"]

    audit = client.security.audit()
    assert isinstance(audit, list)
    assert audit, "registration writes must be audited"
