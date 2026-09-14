"""Experiment mappers: domain snapshots and experiments to wire schemas."""

from __future__ import annotations

from aegis.domain import ExperimentSnapshot

from ..schemas import ExperimentOut, ExperimentSnapshotOut


def snapshot_out(snapshot) -> ExperimentSnapshotOut:
    return ExperimentSnapshotOut(
        target_version_id=snapshot.target_version_id,
        dataset_version_id=snapshot.dataset_version_id,
        evaluator_version_ids=list(snapshot.evaluator_version_ids),
        policy_version_id=snapshot.policy_version_id,
        settings=dict(snapshot.settings),
    )


def snapshot_from_in(payload) -> ExperimentSnapshot:
    """Map an inbound ExperimentSnapshotIn payload to its domain snapshot."""
    return ExperimentSnapshot(
        target_version_id=payload.target_version_id,
        dataset_version_id=payload.dataset_version_id,
        evaluator_version_ids=tuple(payload.evaluator_version_ids),
        policy_version_id=payload.policy_version_id,
        settings=payload.settings,
    )


def experiment_out(experiment) -> ExperimentOut:
    return ExperimentOut(
        id=experiment.id,
        organization_id=experiment.organization_id,
        project_id=experiment.project_id,
        name=experiment.name,
        status=experiment.status.value,
        created_at=experiment.created_at,
        clone_of=experiment.clone_of,
        snapshot=snapshot_out(experiment.snapshot),
    )


__all__ = ["experiment_out", "snapshot_from_in", "snapshot_out"]
