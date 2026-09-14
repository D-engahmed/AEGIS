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
from ..mappers import evaluator_spec_out
from ..schemas import EvaluatorSpecOut

router = APIRouter(prefix="/evaluators", tags=["evaluators"])


@router.get("", response_model=list[EvaluatorSpecOut])
def evaluator_catalog(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
) -> list[EvaluatorSpecOut]:
    """List every scoring plugin available in this deployment."""
    actor.organization.require_membership(actor.context.user_id)
    specs = [evaluator_spec_out(e, requires_trace=False) for e in list_evaluators()]
    for t in list_trajectory_evaluators():
        specs.append(evaluator_spec_out(t, requires_trace=True))
    specs.sort(key=lambda s: s.identity)
    return specs


__all__ = ["router"]
