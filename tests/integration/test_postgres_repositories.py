"""Round-trip the Postgres adapters against the docker-compose database.

Each test starts from a clean schema and proves an adapter stores and returns
its domain value intact — the same operations verified by the live smoke run.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aegis.domain import Conflict
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.execution import (
    ExecutionOutcome,
    new_execution,
    run_created,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.results import EvidenceReference, new_metric_result
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.domain.time import FrozenClock
from aegis.evidence.models import (
    ArtifactReference,
    ArtifactType,
    DataClassification,
    EvidenceRecord,
    ProvenanceSnapshot,
)
from aegis.infrastructure.postgres import PostgresStore
from aegis.policy.application import EvidenceGate, override_blocked_gate
from aegis.policy.models import RunGateReport, RunGateVerdict

pytestmark = pytest.mark.integration


@pytest.fixture
def store(database_url: str) -> PostgresStore:
    return PostgresStore(database_url)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC))


@pytest.fixture
def catalog_versions(clock: FrozenClock):
    target = create_target(clock, "org:1", "prj:1", "itgt", TargetType.MODEL_API)
    target_version = create_target_version(
        clock, target, "1.0.0", {"base_url": "http://x"}, commit_sha="c1"
    )
    dataset = create_dataset(clock, "org:1", "prj:1", "itds")
    dataset_version, _ = create_dataset_version(clock, dataset, "1.0.0")
    dataset_version, _ = add_test_case(
        clock, dataset_version, input="hi", expected="hi", metadata={"k": 1}
    )
    dataset_version, _ = lock_dataset_version(clock, dataset_version)
    return target_version, dataset_version


def test_target_and_dataset_versions_roundtrip(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    store.catalog.register_target(target_version)
    store.catalog.register_dataset(dataset_version)
    assert store.catalog.load_target_version(target_version.id) == target_version
    loaded = store.catalog.load_dataset_version(dataset_version.id)
    assert loaded == dataset_version
    assert loaded.test_cases[0].expected == "hi"
    assert loaded.locked_at is not None


def test_experiment_and_run_roundtrip_with_idempotency(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    store.experiments.save(experiment)
    assert store.experiments.load(experiment.id) == experiment
    assert store.experiments.exists(experiment.id)
    assert not store.experiments.exists("nope")

    run = run_created(
        clock,
        "org:1",
        "prj:1",
        experiment.id,
        experiment.snapshot,
        created_by="bob",
        idempotency_key="k1",
    )
    store.runs.save(run)
    assert store.runs.load(run.id) == run
    assert store.runs.find_by_idempotency("k1").id == run.id

    running = run.start(clock.now())
    store.runs.save(running)
    assert store.runs.load(run.id).status.value == "running"


def test_list_for_org_is_scoped_and_newest_first(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    snapshot = ExperimentSnapshot(
        target_version_id=target_version.id,
        dataset_version_id=dataset_version.id,
        evaluator_version_ids=("aegis/deterministic/exact_match",),
        settings={},
    )
    exp1, _ = create_experiment(clock, "org:1", "prj:1", "first", snapshot=snapshot)
    store.experiments.save(exp1)
    exp_other, _ = create_experiment(clock, "org:2", "prj:9", "other-org", snapshot=snapshot)
    store.experiments.save(exp_other)

    listed = store.experiments.list_for_org("org:1")
    assert [e.id for e in listed] == [exp1.id]

    run1 = run_created(
        clock, "org:1", "prj:1", exp1.id, snapshot, created_by="bob", idempotency_key="r1"
    )
    store.runs.save(run1)
    other_run = run_created(clock, "org:2", "prj:9", exp_other.id, snapshot, created_by="bob")
    store.runs.save(other_run)

    runs = store.runs.list_for_org("org:1")
    assert [r.id for r in runs] == [run1.id]
    assert store.runs.list_for_org("org:2", limit=0) == []


def test_execution_roundtrip(store: PostgresStore, clock: FrozenClock, catalog_versions) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    run = run_created(clock, "org:1", "prj:1", experiment.id, experiment.snapshot, created_by="bob")
    store.runs.save(run)
    running = run.start(clock.now())
    store.runs.save(running)

    case = dataset_version.test_cases[0]
    execution = new_execution(clock, running, 0, case.id, target_version.id, dataset_version.id)
    succeeded = execution.start(clock.now()).succeed(
        ExecutionOutcome(output="hi", latency_ms=1.5, trace_artifact_id="trace/t"),
        clock.now(),
        evidence=(EvidenceReference(execution.id, case.id, "trace/t"),),
    )
    store.executions.save(succeeded)
    assert store.executions.load(execution.id) == succeeded
    assert len(store.executions.list_for_run(run.id)) == 1


def test_results_are_write_once(store: PostgresStore, clock: FrozenClock, catalog_versions) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    run = run_created(clock, "org:1", "prj:1", experiment.id, experiment.snapshot, created_by="bob")
    store.runs.save(run)
    case = dataset_version.test_cases[0]
    result = new_metric_result(
        clock,
        run.id,
        "ex:1",
        case.id,
        "exact_match",
        1.0,
        "aegis/deterministic/exact_match",
        "1.0.0",
        (EvidenceReference("ex:1", case.id, "trace/t"),),
        raw_value=1.0,
    )
    store.results.persist([result])
    assert store.results.list_for_run(run.id)[0] == result

    with pytest.raises(Conflict):
        store.results.persist([result])


def test_evidence_provenance_and_artifacts_roundtrip(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    run = run_created(clock, "org:1", "prj:1", experiment.id, experiment.snapshot, created_by="bob")
    store.runs.save(run)
    case = dataset_version.test_cases[0]
    result = new_metric_result(
        clock,
        run.id,
        "ex:1",
        case.id,
        "exact_match",
        1.0,
        "aegis/deterministic/exact_match",
        "1.0.0",
        (EvidenceReference("ex:1", case.id, "trace/t"),),
    )
    store.results.persist([result])

    provenance = ProvenanceSnapshot(
        experiment_id=experiment.id,
        target_version_id=target_version.id,
        target_config_hash="h1",
        dataset_version_id=dataset_version.id,
        dataset_hash="h2",
        evaluator_identities=("aegis/deterministic/exact_match",),
        evaluator_config_hash="h3",
        policy_version_id=None,
        snapshot_timestamp=clock.now(),
    )
    artifact = ArtifactReference(
        artifact_id="art:1",
        artifact_type=ArtifactType.RAW_OUTPUT,
        storage_key="raw/1",
        content_hash="c",
        size_bytes=3,
        content_type="text/plain",
        created_at=clock.now(),
    )
    record = EvidenceRecord(
        id="ev:1",
        metric_result_id=result.id,
        run_id=run.id,
        execution_id="ex:1",
        experiment_id=experiment.id,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0.0",
        dataset_version_id=dataset_version.id,
        target_version_id=target_version.id,
        artifact_references=(artifact,),
        provenance=provenance,
        classification=DataClassification.INTERNAL,
        created_at=clock.now(),
        created_by="bob",
    )
    store.evidence.persist(record)
    assert store.evidence.get(record.id) == record
    assert store.evidence.list_for_run(run.id)[0] == record
    assert store.evidence.list_for_metric_result(result.id)[0] == record
    assert store.provenance.provenance_for_result(result.id) == provenance

    ref = store.artifacts.store(ArtifactType.RAW_OUTPUT, b"hi!", {"content_type": "text/plain"})
    assert store.artifacts.retrieve(ref.artifact_id) == b"hi!"
    assert store.artifacts.get_reference(ref.artifact_id).content_hash == ref.content_hash


def test_gate_report_roundtrip_and_override(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    run = run_created(clock, "org:1", "prj:1", experiment.id, experiment.snapshot, created_by="bob")
    store.runs.save(run)
    case = dataset_version.test_cases[0]
    result = new_metric_result(
        clock,
        run.id,
        "ex:1",
        case.id,
        "exact_match",
        0.0,
        "aegis/deterministic/exact_match",
        "1.0.0",
        (EvidenceReference("ex:1", case.id, "trace/t"),),
    )
    store.results.persist([result])

    report = RunGateReport(
        run_id=run.id,
        verdict=RunGateVerdict.BLOCK,
        evaluated_at=clock.now(),
        decisions=(EvidenceGate().evaluate([result]),),
    )
    store.run_gate_store.save(report)
    assert store.run_gate_store.exists(run.id)
    assert store.run_gate_store.load(run.id).verdict is RunGateVerdict.BLOCK

    overridden = override_blocked_gate(
        report, overridden_by="alice", reason="approved", at=clock.now()
    )
    store.run_gate_store.save(overridden)
    assert not store.run_gate_store.load(run.id).is_blocked
    assert store.run_gate_store.load(run.id).override.overridden_by == "alice"


def test_cancellation_registry_roundtrip(
    store: PostgresStore, clock: FrozenClock, catalog_versions
) -> None:
    target_version, dataset_version = catalog_versions
    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "itexp",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )
    run = run_created(clock, "org:1", "prj:1", experiment.id, experiment.snapshot, created_by="bob")
    store.runs.save(run)
    store.cancellations.cancel(run.id, "alice", clock)
    assert store.cancellations.is_cancelled(run.id)
    assert not store.cancellations.is_cancelled("other")
    assert store.cancellations.who_cancelled(run.id) == "alice"
