"""Observability endpoints: health, cost, and preserved evaluation traces."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..mappers import cost_out, health_summary_out, trace_out
from ..schemas import HealthSummaryOut

router = APIRouter(prefix="/observability", tags=["observability"])

health_router = APIRouter(prefix="/health", tags=["observability"])


@health_router.get("/live", response_model=HealthSummaryOut)
def liveness(
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> HealthSummaryOut:
    """Liveness probe: aggregate of registered health checks."""
    actor.organization.require_membership(actor.context.user_id)
    return health_summary_out(container.health.aggregate(), container.health.is_healthy())


@router.get("/cost/{run_id}")
def run_cost(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, float]:
    """Per-run AI spend, target separated from evaluator cost."""
    actor.organization.require_membership(actor.context.user_id)
    container.run_service.require_run(actor.organization, run_id)
    return cost_out(
        container.cost.total_cost(run_id),
        container.cost.target_cost(run_id),
        container.cost.evaluator_cost(run_id),
    )


@router.get("/traces/{run_id}")
def run_traces(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[dict[str, object]]:
    """Preserved evaluation traces (never sampled) for a run."""
    actor.organization.require_membership(actor.context.user_id)
    container.run_service.require_run(actor.organization, run_id)
    records = container.preservation.traces_for_run(run_id)
    return [trace_out(t) for t in records]


__all__ = ["health_router", "router"]
