"""Policy endpoints: run gate verdicts and authorized overrides.

A blocked run carries its evidence-recorded report; only owners/admins (never a
service account) may override, and every override is audited
(deployment-strategy.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from aegis.policy.models import RunGateReport
from aegis.security.models import Permission
from aegis.security.override import can_override_gate

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..schemas import GateDecisionOut, GateOverrideIn, RunVerdictOut

router = APIRouter(prefix="/policy", tags=["policy"])


def _verdict_out(report: RunGateReport) -> RunVerdictOut:
    return RunVerdictOut(
        run_id=report.run_id,
        verdict=report.verdict.value,
        decisions=[
            GateDecisionOut(
                gate_id=d.gate_id,
                verdict=d.verdict.value,
                reason=d.reason,
                severity=d.severity.value,
            )
            for d in report.decisions
        ],
        evaluated_at=report.evaluated_at,
        overridden=report.override is not None,
        override=(
            {
                "overridden_by": report.override.overridden_by,
                "reason": report.override.reason,
                "overridden_at": report.override.overridden_at,
                "gate_ids": list(report.override.gate_ids),
            }
            if report.override is not None
            else None
        ),
    )


@router.get("/verdict/{run_id}", response_model=RunVerdictOut)
def run_verdict(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> RunVerdictOut:
    """Fetch the persisted gate report (verdict + decisions) for a run."""
    actor.organization.require_membership(actor.context.user_id)
    try:
        report = container.run_gates.report(run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no gate report for run {run_id!r}",
        ) from exc
    return _verdict_out(report)


@router.post("/verdict/{run_id}/override", response_model=RunVerdictOut, status_code=200)
def override_run_block(
    run_id: str,
    payload: GateOverrideIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.POLICY_OVERRIDE))],
    container: Annotated[Container, Depends(get_container)],
) -> RunVerdictOut:
    """Authorize proceeding past a blocked run; recorded and audited."""
    actor.organization.require_membership(actor.context.user_id)
    try:
        report = container.run_gates.report(run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no gate report for run {run_id!r}",
        ) from exc
    decision_to_override = next((d for d in report.decisions if d.severity.blocks), None)
    if decision_to_override is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run is not blocked; nothing to override",
        )
    if not can_override_gate(actor.context, decision_to_override):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="actor may not override this gate decision",
        )
    updated = container.run_gates.override(
        report,
        overridden_by=actor.context.user_id,
        reason=payload.reason,
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
    return _verdict_out(updated)


@router.get("/now", include_in_schema=False)
def policy_time() -> str:
    from aegis.domain.time import UTC

    return datetime.now(UTC).isoformat()


__all__ = ["router"]
