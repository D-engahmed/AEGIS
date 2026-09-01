"""Experiments: reproducible configuration snapshots (Phase 2).

An Experiment is a snapshot of the full evaluation configuration (target
version, dataset version, evaluators, policy, settings). Once execution begins
the snapshot is immutable; the only way to change what a run means is to clone
the experiment into a new variant (immutability-rules.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .events import DomainEvent
from .exceptions import ImmutableResourceViolation, ValidationFailed
from .identifiers import new_id
from .time import Clock


class ExperimentStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def configurable(self) -> bool:
        return self is ExperimentStatus.CREATED

    @property
    def terminal(self) -> bool:
        return self in (
            ExperimentStatus.SUCCEEDED,
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
        )


@dataclass(frozen=True)
class ExperimentSnapshot:
    """The immutable evaluation configuration pinned at creation time."""

    target_version_id: str
    dataset_version_id: str
    evaluator_version_ids: tuple[str, ...] = ()
    policy_version_id: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_version_id:
            raise ValidationFailed("experiment snapshot requires a target version")
        if not self.dataset_version_id:
            raise ValidationFailed("experiment snapshot requires a dataset version")
        if not isinstance(self.settings, Mapping):
            raise ValidationFailed("experiment settings must be a mapping")


@dataclass(frozen=True)
class Experiment:
    id: str
    organization_id: str
    project_id: str
    name: str
    snapshot: ExperimentSnapshot
    created_at: datetime
    status: ExperimentStatus = ExperimentStatus.CREATED
    clone_of: str | None = None

    def ensure_configurable(self) -> None:
        """Guard: updates are only legal before execution begins."""
        if not self.status.configurable:
            raise ImmutableResourceViolation(
                f"experiment {self.id!r} is {self.status.value}; its snapshot is immutable"
            )

    def start(self) -> Experiment:
        """Move from created to running; after this the snapshot is immutable."""
        self.ensure_configurable()
        return _replace_status(self, ExperimentStatus.RUNNING)

    def clone(self, clock: Clock, name: str | None = None) -> Experiment:
        """Create a separate comparison variant; the original is untouched."""
        return Experiment(
            id=new_id("exp"),
            organization_id=self.organization_id,
            project_id=self.project_id,
            name=name or f"{self.name} (clone)",
            snapshot=self.snapshot,
            created_at=clock.now(),
            status=ExperimentStatus.CREATED,
            clone_of=self.id,
        )


def _replace_status(experiment: Experiment, status: ExperimentStatus) -> Experiment:
    from dataclasses import replace

    return replace(experiment, status=status)


def create_experiment(
    clock: Clock,
    organization_id: str,
    project_id: str,
    name: str,
    snapshot: ExperimentSnapshot | None = None,
    **settings: Any,
) -> tuple[Experiment, DomainEvent]:
    """Create a new experiment definition backed by an immutable snapshot."""
    if not name or not name.strip():
        raise ValidationFailed("experiment name must not be empty")
    if snapshot is None:
        raise ValidationFailed("an experiment requires a configuration snapshot")
    experiment = Experiment(
        id=new_id("exp"),
        organization_id=organization_id,
        project_id=project_id,
        name=name.strip(),
        snapshot=snapshot,
        created_at=clock.now(),
    )
    from .events import emit

    event = emit(
        clock,
        "experiment.created",
        "Experiment",
        experiment.id,
        organization_id=organization_id,
        project_id=project_id,
        name=experiment.name,
        target_version_id=snapshot.target_version_id,
        dataset_version_id=snapshot.dataset_version_id,
    )
    return experiment, event


__all__ = [
    "Experiment",
    "ExperimentSnapshot",
    "ExperimentStatus",
    "create_experiment",
]
