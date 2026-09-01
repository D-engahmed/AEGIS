"""Observability endpoints: health, cost, and preserved evaluation traces."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..schemas import HealthCheckOut, HealthSummaryOut

router = APIRouter(prefix="/observability", tags=["observability"])

health_router = APIRouter(prefix="/health", tags=["observability"])


@health_router.get("/live", response_model=HealthSummaryOut)
def liveness(
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> HealthSummaryOut:
    """Liveness probe: aggregate of registered health checks."""
    actor.organization.require_membership(actor.context.user_id)
    checks = [
        HealthCheckOut(name=name, status=status_value)
        for name, status_value in container.health.aggregate().items()
    ]
    return HealthSummaryOut(
        overall="healthy" if container.health.is_healthy() else "unhealthy",
        checks=checks,
    )


@router.get("/cost/{run_id}")
def run_cost(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, float]:
    """Per-run AI spend, target separated from evaluator cost."""
    actor.organization.require_membership(actor.context.user_id)
    return {
        "total_usd": container.cost.total_cost(run_id),
        "target_usd": container.cost.target_cost(run_id),
        "evaluator_usd": container.cost.evaluator_cost(run_id),
    }


@router.get("/traces/{run_id}")
def run_traces(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[dict[str, object]]:
    """Preserved evaluation traces (never sampled) for a run."""
    actor.organization.require_membership(actor.context.user_id)
    records = container.preservation.traces_for_run(run_id)
    return [
        {
            "trace_id": t.trace_id,
            "run_id": t.run_id,
            "execution_id": t.execution_id,
            "span_count": len(t.spans),
            "preserved_at": t.preserved_at,
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "status": s.status.value,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "attributes": dict(s.attributes),
                }
                for s in t.spans
            ],
        }
        for t in records
    ]


__all__ = ["health_router", "router"]
