"""Experiment endpoints: CRUD over reproducible configuration snapshots."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aegis.security.models import Permission

from ..container import Container
from ..deps import (
    Actor,
    audit,
    get_container,
    require_permission,
)
from ..mappers import experiment_out, run_out, snapshot_from_in
from ..schemas import ExperimentCreateIn, ExperimentOut, RunOut

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentOut])
def list_experiments(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[ExperimentOut]:
    """List experiments within the caller's tenant, newest first."""
    experiments = container.experiment_service.list(actor.organization, actor.context.user_id)
    return [experiment_out(e) for e in experiments]


@router.get("/{experiment_id}/runs", response_model=list[RunOut])
def list_experiment_runs(
    experiment_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[RunOut]:
    """List runs for an experiment within the caller's tenant, newest first."""
    views = container.run_service.list(
        actor.organization, actor.context.user_id, experiment_id=experiment_id
    )
    return [run_out(v) for v in views]


@router.post("", response_model=ExperimentOut, status_code=201)
def create_experiment(
    payload: ExperimentCreateIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_CREATE))],
    container: Annotated[Container, Depends(get_container)],
) -> ExperimentOut:
    """Create a new experiment from an immutable configuration snapshot."""
    snapshot = snapshot_from_in(payload.snapshot)
    experiment = container.experiment_service.create(
        actor.organization,
        actor.context.user_id,
        payload.project_id,
        payload.name,
        snapshot,
    )
    audit(
        container,
        actor,
        "experiment.created",
        "experiment",
        experiment.id,
    )
    return experiment_out(experiment)


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(
    experiment_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> ExperimentOut:
    """Fetch a single experiment within the caller's tenant."""
    experiment = container.experiment_service.get(
        actor.organization, actor.context.user_id, experiment_id
    )
    return experiment_out(experiment)


@router.post("/{experiment_id}/clone", response_model=ExperimentOut, status_code=201)
def clone_experiment(
    experiment_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_CREATE))],
    container: Annotated[Container, Depends(get_container)],
) -> ExperimentOut:
    """Clone an experiment as a separate comparison variant."""
    experiment = container.experiment_service.clone(
        actor.organization, actor.context.user_id, experiment_id
    )
    audit(container, actor, "experiment.cloned", "experiment", experiment.id)
    return experiment_out(experiment)


@router.post("/{experiment_id}/start", response_model=ExperimentOut)
def start_experiment(
    experiment_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_START))],
    container: Annotated[Container, Depends(get_container)],
) -> ExperimentOut:
    """Lock the snapshot and begin execution."""
    experiment = container.experiment_service.start(
        actor.organization, actor.context.user_id, experiment_id
    )
    audit(container, actor, "experiment.started", "experiment", experiment.id)
    return experiment_out(experiment)


__all__ = ["router"]
