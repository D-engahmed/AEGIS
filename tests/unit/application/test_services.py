"""Application services: idempotent submits, cancellation transitions, auth."""

import pytest

from aegis.application.services import ExperimentService, RunService
from aegis.domain import (
    InsufficientPermission,
    InvalidState,
    NotFound,
    RunStatus,
)
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.execution import ExperimentSnapshot
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.domain.tenants import Membership, Organization, Role
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryExperimentRepository,
    MemoryQueue,
    MemoryRunRepository,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def org(clock) -> Organization:
    organization = Organization(id="org:1", name="ACME", created_at=clock.now())
    return Organization(
        id=organization.id,
        name=organization.name,
        created_at=organization.created_at,
        members=(Membership(organization.id, "alice", Role.OWNER),),
    )


@pytest.fixture
def data(clock):
    target = create_target(clock, "org:1", "prj:1", "svc-chat", TargetType.LLM_APPLICATION)
    tv = create_target_version(clock, target, "1.0.0", config={"model": "fake"})
    dataset = create_dataset(clock, "org:1", "prj:1", "qa")
    dv = create_dataset_version(clock, dataset, "1.0.0")[0]
    dv, _ = add_test_case(clock, dv, input="hi", expected="hello")
    dv = lock_dataset_version(clock, dv)[0]
    return tv, dv


@pytest.fixture
def services(clock, data, org):
    tv, dv = data
    experiments = MemoryExperimentRepository()
    runs = MemoryRunRepository()
    catalog = InMemoryDataCatalog()
    catalog.register_target(tv)
    catalog.register_dataset(dv)
    cancellations = InMemoryCancellationRegistry()
    queue = MemoryQueue()
    return {
        "experiments": experiments,
        "runs": runs,
        "catalog": catalog,
        "cancellations": cancellations,
        "queue": queue,
        "org": org,
        "experiment_service": ExperimentService(experiments, clock),
        "run_service": RunService(experiments, runs, catalog, cancellations, queue, clock),
        "snapshot": ExperimentSnapshot(
            target_version_id=tv.id,
            dataset_version_id=dv.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
        ),
    }


def test_submit_run_is_idempotent(services) -> None:
    experiment = services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-a", services["snapshot"]
    )
    first = services["run_service"].submit(
        services["org"], "alice", experiment.id, idempotency_key="k-1"
    )
    replay = services["run_service"].submit(
        services["org"], "alice", experiment.id, idempotency_key="k-1"
    )
    assert replay.run_id == first.run_id
    assert services["queue"].pending() == 1
    assert first.status == RunStatus.QUEUED.value


def test_submit_validates_snapshot_against_catalog(services) -> None:
    services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-b", services["snapshot"]
    )
    bad_snapshot = ExperimentSnapshot(target_version_id="tvr:nope", dataset_version_id="dsv:nope")
    bad = services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-bad", bad_snapshot
    )
    with pytest.raises(NotFound):
        services["run_service"].submit(services["org"], "alice", bad.id)


def test_cancel_rejects_terminal_run(services) -> None:
    experiment = services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-c", services["snapshot"]
    )
    run_view = services["run_service"].submit(services["org"], "alice", experiment.id)
    services["run_service"].cancel(services["org"], "alice", run_view.run_id)
    with pytest.raises(InvalidState):
        services["run_service"].cancel(services["org"], "alice", run_view.run_id)


def test_experiment_start_makes_snapshot_immutable(services) -> None:
    experiment = services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-d", services["snapshot"]
    )
    started = services["experiment_service"].start(services["org"], "alice", experiment.id)
    assert started.status.value == "running"
    from aegis.domain import ImmutableResourceViolation

    with pytest.raises(ImmutableResourceViolation):
        started.start()


def test_non_member_cannot_act(services) -> None:
    experiment = services["experiment_service"].create(
        services["org"], "alice", "prj:1", "exp-e", services["snapshot"]
    )
    with pytest.raises(InsufficientPermission):
        services["run_service"].submit(services["org"], "mallory", experiment.id)
