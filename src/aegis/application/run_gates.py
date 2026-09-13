"""Run gate orchestration: evaluate, persist, and authorize overrides (layer 08).

The gate result is a first-class persisted artifact so consumers can answer
"what blocked this run and who unblocked it" without re-running metrics —
matching the no-decision-without-record invariant of the approval workflow.
"""

from __future__ import annotations

from aegis.domain.time import Clock
from aegis.policy.application import (
    Gate,
    RunGateReport,
    evaluate_run_gates,
    override_blocked_gate,
)
from aegis.policy.models import RunGateVerdict
from aegis.policy.ports import RunGateStore
from aegis.security.models import AuthContext
from aegis.security.override import can_override_gate


class RunGateService:
    """Commands for evaluating runs against policy and recording overrides."""

    def __init__(
        self,
        store: RunGateStore,
        clock: Clock,
        gates: tuple[Gate, ...] = (),
    ) -> None:
        self._store = store
        self._clock = clock
        self._gates = gates

    def evaluate(
        self,
        run,
        results: list,
        *,
        gates: tuple[Gate, ...] | None = None,
    ) -> RunGateReport:
        report = evaluate_run_gates(run, results, gates=self._gates if gates is None else gates)
        self._store.save(report)
        return report

    def report(self, run_id: str) -> RunGateReport:
        return self._store.load(run_id)

    def override(
        self,
        report: RunGateReport,
        overridden_by: str,
        reason: str,
    ) -> RunGateReport:
        if not reason.strip():
            from aegis.domain import ValidationFailed

            raise ValidationFailed("an override requires a reason")
        updated = override_blocked_gate(
            report,
            overridden_by=overridden_by,
            reason=reason.strip(),
            at=self._clock.now(),
        )
        self._store.save(updated)
        return updated

    def override_blocked(
        self,
        run_id: str,
        reason: str,
        auth_context: AuthContext,
    ) -> RunGateReport:
        """Orchestrate: load, find blocking decision, authorize, override, save.

        The caller (interface layer) keeps HTTP error mapping, DTO conversion,
        and audit recording.  This method owns only the business-logic steps
        that belong in the application layer.
        """
        from aegis.domain import Conflict, InsufficientPermission, NotFound

        try:
            report = self._store.load(run_id)
        except NotFound:
            raise
        except Exception:
            raise NotFound(f"gate report for run {run_id!r} not found") from None

        decision_to_override = next((d for d in report.decisions if d.severity.blocks), None)
        if decision_to_override is None:
            raise Conflict("run is not blocked; nothing to override")

        if not can_override_gate(auth_context, decision_to_override):
            raise InsufficientPermission("actor may not override this gate decision")

        return self.override(
            report,
            overridden_by=auth_context.user_id,
            reason=reason,
        )


def is_run_blocked(report: RunGateReport) -> bool:
    """Convenience predicate for callers that gate on the persisted verdict."""
    return report.verdict is RunGateVerdict.BLOCK and report.override is None


__all__ = ["RunGateService", "is_run_blocked"]
