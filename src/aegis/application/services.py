"""Application services: use-case orchestration over domain + ports.

No raw SQL, no HTTP framework, no queue client internals. Authorization is
checked here before any domain operation executes.
"""

from __future__ import annotations

from aegis.domain import (
    Experiment,
    ExperimentSnapshot,
    ExperimentStatus,
    InvalidState,
    NotFound,
)
from aegis.domain.experiments import create_experiment
from aegis.domain.tenants import Organization
from aegis.domain.time import Clock

from .dtos import RunView
from .ports import (
    CancellationRegistry,
    DataCatalog,
    ExperimentRepository,
    Queue,
    RunRepository,
)


class ExperimentService:
    """Commands for experiment definitions: create, clone, start."""

    def __init__(self, experiments: ExperimentRepository, clock: Clock) -> None:
        self._experiments = experiments
        self._clock = clock

    def _require_member(self, organization: Organization, actor: str) -> None:
        organization.require_membership(actor)

    def create(
        self,
        organization: Organization,
        actor: str,
        project_id: str,
        name: str,
        snapshot: ExperimentSnapshot,
    ) -> Experiment:
        self._require_member(organization, actor)
        experiment, _event = create_experiment(
            self._clock,
            organization.id,
            project_id,
            name,
            snapshot,
        )
        self._experiments.save(experiment)
        return experiment

    def get(self, organization: Organization, actor: str, experiment_id: str) -> Experiment:
        self._require_member(organization, actor)
        return self._load(experiment_id)

    def clone(
        self,
        organization: Organization,
        actor: str,
        experiment_id: str,
        new_name: str | None = None,
    ) -> Experiment:
        """Clone an existing experiment as a separate compare variant."""
        self._require_member(organization, actor)
        source = self._load(experiment_id)
        clone = source.clone(self._clock, name=new_name)
        self._experiments.save(clone)
        return clone

    def start(
        self,
        organization: Organization,
        actor: str,
        experiment_id: str,
    ) -> Experiment:
        """Begin execution; the experiment snapshot becomes immutable."""
        self._require_member(organization, actor)
        experiment = self._load(experiment_id)
        started = experiment.start()
        self._experiments.save(started)
        return started

    def _load(self, experiment_id: str) -> Experiment:
        if not self._experiments.exists(experiment_id):
            raise NotFound(experiment_id)
        return self._experiments.load(experiment_id)


class RunService:
    """Commands for asynchronous runs: submit (idempotent), cancel, status."""

    def __init__(
        self,
        experiments: ExperimentRepository,
        runs: RunRepository,
        catalog: DataCatalog,
        cancellations: CancellationRegistry,
        queue: Queue,
        clock: Clock,
    ) -> None:
        self._experiments = experiments
        self._runs = runs
        self._catalog = catalog
        self._cancellations = cancellations
        self._queue = queue
        self._clock = clock

    def submit(
        self,
        organization: Organization,
        actor: str,
        experiment_id: str,
        idempotency_key: str | None = None,
    ) -> RunView:
        """Validate, start execution, and enqueue the run.

        Replays of the same idempotency key return the original run without
        creating a duplicate (async-execution-contract.md).
        """
        organization.require_membership(actor)
        if idempotency_key:
            existing = self._runs.find_by_idempotency(idempotency_key)
            if existing is not None:
                return RunView.from_run(existing)

        experiment = self._experiments.load(experiment_id)
        self._validate_snapshot(experiment)
        started_experiment = (
            experiment.start() if experiment.status is ExperimentStatus.CREATED else experiment
        )
        # snapshots are validated once; the run pins the experiment snapshot
        from aegis.domain.execution import run_created

        run = run_created(
            self._clock,
            organization.id,
            experiment.project_id,
            started_experiment.id,
            started_experiment.snapshot,
            created_by=actor,
            idempotency_key=idempotency_key,
        )
        self._experiments.save(started_experiment)
        self._runs.save(run)
        self._queue.put(run.id)
        return RunView.from_run(run)

    def cancel(
        self,
        organization: Organization,
        actor: str,
        run_id: str,
    ) -> RunView:
        organization.require_membership(actor)
        run = self._runs.load(run_id)
        if run.status.terminal:
            raise InvalidState(f"run {run_id!r} is already {run.status.value}")
        cancelled = run.cancel(actor, self._clock.now(), summary=run.evidence_summary)
        self._cancellations.cancel(run.id, actor, self._clock)
        self._runs.save(cancelled)
        return RunView.from_run(cancelled)

    def status(
        self,
        organization: Organization,
        actor: str,
        run_id: str,
    ) -> RunView:
        organization.require_membership(actor)
        return RunView.from_run(self._runs.load(run_id))

    def _validate_snapshot(self, experiment: Experiment) -> None:
        self._catalog.load_target_version(experiment.snapshot.target_version_id)
        self._catalog.load_dataset_version(experiment.snapshot.dataset_version_id)


__all__ = ["ExperimentService", "RunService"]
