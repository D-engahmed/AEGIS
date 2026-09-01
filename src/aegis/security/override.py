"""Gate override authority: who may override a blocked promotion decision.

Only owners and admins may override a safety BLOCK, and a service account never
may. This is the security layer's contribution to the deployment gate
(docs/ci-cd/deployment-strategy.md).
"""

from __future__ import annotations

from aegis.policy.models import GateDecision, Verdict
from aegis.security.models import AuthContext

from .models import AuthMethod


def can_override_gate(context: AuthContext, decision: GateDecision) -> bool:
    """True when the actor may override a non-passing gate decision."""
    if decision.verdict is Verdict.PASS:
        return False
    if not context.can_override_gates:
        return False
    return context.authentication_method is not AuthMethod.SERVICE_ACCOUNT


__all__ = ["can_override_gate"]
