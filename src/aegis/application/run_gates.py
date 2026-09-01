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


class RunGateService:
    """Commands for evaluating runs against policy and recording overrides."""

    def __init__(self, store: RunGateStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def evaluate(
        self,
        run,
        results: list,
        *,
        gates: tuple[Gate, ...] = (),
    ) -> RunGateReport:
        report = evaluate_run_gates(run, results, gates=gates)
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


def is_run_blocked(report: RunGateReport) -> bool:
    """Convenience predicate for callers that gate on the persisted verdict."""
    return report.verdict is RunGateVerdict.BLOCK and report.override is None


__all__ = ["RunGateService", "is_run_blocked"]
