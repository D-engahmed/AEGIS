"""In-memory adapters: write-once results, queue semantics, cancellation."""

import pytest

from aegis.domain import Conflict, NotFound, Run, new_metric_result
from aegis.domain.execution import ExperimentSnapshot
from aegis.domain.time import FrozenClock
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryExecutionRepository,
    MemoryExperimentRepository,
    MemoryQueue,
    MemoryResultRepository,
    MemoryRunRepository,
)

pytestmark = pytest.mark.unit


def _metric(clock, metric_id="mtr:1"):
    from aegis.domain import EvidenceReference

    return new_metric_result(
        clock,
        run_id="run:1",
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=1.0,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0.0",
        evidence=(
            EvidenceReference(
                execution_id="exe:1",
                dataset_case_id="tc:1",
                trace_artifact_id="trace/1",
            ),
        ),
    )


def test_result_repository_is_write_once() -> None:
    clock = FrozenClock()
    repo = MemoryResultRepository()
    metric = _metric(clock)
    repo.persist([metric])
    with pytest.raises(Conflict):
        repo.persist([metric])
    assert len(repo.list_for_run("run:1")) == 1


def test_queue_claim_complete_abandon() -> None:
    queue = MemoryQueue(["run:1", "run:2"])
    assert queue.pending() == 2
    assert queue.claim() == "run:1"
    assert queue.pending() == 1
    assert queue.claimed_ids == {"run:1"}
    queue.abandon("run:1")
    assert queue.pending() == 2
    assert queue.claim() == "run:1"
    queue.complete("run:1")
    assert queue.claim() == "run:2"
    queue.complete("run:2")
    assert queue.claim() is None


def test_run_repository_idempotency_lookup() -> None:
    clock = FrozenClock()
    run = Run(
        id="run:1",
        organization_id="org:1",
        project_id="prj:1",
        experiment_id="exp:1",
        snapshot=ExperimentSnapshot(target_version_id="tvr:1", dataset_version_id="dsv:1"),
        created_by="alice",
        created_at=clock.now(),
        idempotency_key="idem-1",
    )
    repo = MemoryRunRepository()
    repo.save(run)
    assert repo.find_by_idempotency("idem-1") is run
    assert repo.find_by_idempotency("missing") is None
    assert repo.load("run:1") is run
    with pytest.raises(NotFound):
        repo.load("run:missing")


def test_catalog_and_experiment_repository() -> None:
    clock = FrozenClock()
    catalog = InMemoryDataCatalog()
    from aegis.domain.datasets import create_dataset, create_dataset_version
    from aegis.domain.experiments import create_experiment
    from aegis.domain.targets import TargetType, create_target, create_target_version

    target = create_target(clock, "org:1", "prj:1", "t", TargetType.AGENT)
    tv = create_target_version(clock, target, "1.0.0", config={})
    dataset = create_dataset(clock, "org:1", "prj:1", "d")
    dv = create_dataset_version(clock, dataset, "1.0.0")[0]
    catalog.register_target(tv)
    catalog.register_dataset(dv)
    assert catalog.load_target_version(tv.id) is tv
    with pytest.raises(NotFound):
        catalog.load_target_version("tvr:nope")

    experiments = MemoryExperimentRepository()
    experiment = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "exp",
        ExperimentSnapshot(target_version_id=tv.id, dataset_version_id=dv.id),
    )[0]
    experiments.save(experiment)
    assert experiments.exists(experiment.id)
    assert experiments.load(experiment.id) is experiment


def test_execution_repository_indexes_by_run() -> None:
    clock = FrozenClock()
    repo = MemoryExecutionRepository()
    from aegis.domain import ExecutionRecord

    a = ExecutionRecord(
        id="exe:a",
        run_id="run:1",
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=clock.now(),
    )
    b = ExecutionRecord(
        id="exe:b",
        run_id="run:2",
        sequence=0,
        test_case_id="tc:2",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=clock.now(),
    )
    repo.save(a)
    repo.save(b)
    assert [ex.id for ex in repo.list_for_run("run:1")] == ["exe:a"]
    with pytest.raises(NotFound):
        repo.load("exe:missing")


def test_cancellation_registry_tokens() -> None:
    clock = FrozenClock()
    registry = InMemoryCancellationRegistry()
    registry.cancel("run:1", "alice", clock)
    assert registry.is_cancelled("run:1")
    assert registry.who_cancelled("run:1") == "alice"
    registry.clear()
    assert not registry.is_cancelled("run:1")
