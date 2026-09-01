"""Run endpoints: submit (idempotent), status, cancel, and result listing."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, audit, get_container, require_permission
from ..schemas import MetricResultOut, RunOut, RunSubmitIn
from .results import metric_result_out

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
def submit_run(
    payload: RunSubmitIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_START))],
    container: Annotated[Container, Depends(get_container)],
) -> RunOut:
    """Submit a run; replays of the same idempotency key return the original."""
    view = container.run_service.submit(
        actor.organization,
        actor.context.user_id,
        payload.experiment_id,
        payload.idempotency_key,
    )
    audit(container, actor, "run.submitted", "run", view.run_id)
    return RunOut(**asdict(view))


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> RunOut:
    """Fetch the current status of a run."""
    view = container.run_service.status(actor.organization, actor.context.user_id, run_id)
    return RunOut(**asdict(view))


@router.post("/{run_id}/cancel", response_model=RunOut)
def cancel_run(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_CANCEL))],
    container: Annotated[Container, Depends(get_container)],
) -> RunOut:
    """Request cooperative cancellation of a run."""
    view = container.run_service.cancel(actor.organization, actor.context.user_id, run_id)
    audit(container, actor, "run.cancelled", "run", run_id)
    return RunOut(**asdict(view))


@router.get("/{run_id}/results", response_model=list[MetricResultOut])
def list_run_results(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    metric_name: Annotated[str | None, Query()] = None,
) -> list[MetricResultOut]:
    """List the metric results produced for a run (optionally filtered)."""
    actor.organization.require_membership(actor.context.user_id)
    results = container.results.list_for_run(run_id)
    if metric_name is not None:
        results = [r for r in results if r.metric_name == metric_name]
    return [metric_result_out(r) for r in results]


__all__ = ["router"]
