"""Evaluator discovery endpoints: the scoring plugins a client may pin.

Lists the deterministic plugin registry plus the trajectory evaluators
(requires_trace=True). Identity strings are the values an experiment's
snapshot pins in ``evaluator_version_ids``, so discovery makes the SDK
self-configuring.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aegis.evaluation.plugins import list_evaluators
from aegis.evaluation.trajectory import list_trajectory_evaluators
from aegis.security.models import Permission

from ..deps import Actor, require_permission
from ..schemas import EvaluatorSpecOut

router = APIRouter(prefix="/evaluators", tags=["evaluators"])


@router.get("", response_model=list[EvaluatorSpecOut])
def evaluator_catalog(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
) -> list[EvaluatorSpecOut]:
    """List every scoring plugin available in this deployment."""
    actor.organization.require_membership(actor.context.user_id)
    specs = [
        EvaluatorSpecOut(
            identity=e.identity,
            version=e.version,
            display_name=e.display_name,
            metrics=list(e.metrics),
            requires_trace=False,
            severity=e.severity,
            unit=e.unit,
        )
        for e in list_evaluators()
    ]
    for t in list_trajectory_evaluators():
        specs.append(
            EvaluatorSpecOut(
                identity=t.identity,
                version=t.version,
                display_name=t.display_name,
                metrics=list(t.metrics),
                requires_trace=True,
                severity=t.severity,
                unit=t.unit,
            )
        )
    specs.sort(key=lambda s: s.identity)
    return specs


__all__ = ["router"]