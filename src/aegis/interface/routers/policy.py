"""Policy endpoints: run gate verdicts and authorized overrides.

A blocked run carries its evidence-recorded report; only owners/admins (never a
service account) may override, and every override is audited
(deployment-strategy.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..mappers import verdict_out
from ..schemas import GateOverrideIn, RunVerdictOut

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/verdict/{run_id}", response_model=RunVerdictOut)
def run_verdict(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> RunVerdictOut:
    """Fetch the persisted gate report (verdict + decisions) for a run."""
    actor.organization.require_membership(actor.context.user_id)
    report = container.run_gates.report(run_id)
    return verdict_out(report)


@router.post("/verdict/{run_id}/override", response_model=RunVerdictOut, status_code=200)
def override_run_block(
    run_id: str,
    payload: GateOverrideIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.POLICY_OVERRIDE))],
    container: Annotated[Container, Depends(get_container)],
) -> RunVerdictOut:
    """Authorize proceeding past a blocked run; recorded and audited."""
    actor.organization.require_membership(actor.context.user_id)
    updated = container.run_gates.override_blocked(
        run_id,
        payload.reason,
        actor.context,
    )
    container.audit.record(
        actor_id=actor.context.user_id,
        action="gate.overridden",
        resource_type="run",
        resource_id=run_id,
        organization_id=actor.context.organization_id,
        timestamp=container.clock.now(),
        metadata={
            "reason": payload.reason,
            "gate_ids": list(updated.override.gate_ids) if updated.override else [],
        },
    )
    return verdict_out(updated)


@router.get("/now", include_in_schema=False)
def policy_time() -> str:
    from aegis.domain.time import UTC

    return datetime.now(UTC).isoformat()


__all__ = ["router"]
