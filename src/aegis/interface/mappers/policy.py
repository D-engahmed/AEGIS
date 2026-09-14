"""Policy mappers: gate reports and decisions to wire schemas."""

from __future__ import annotations

from aegis.policy.models import RunGateReport

from ..schemas import GateDecisionOut, RunVerdictOut


def decision_out(decision) -> GateDecisionOut:
    return GateDecisionOut(
        gate_id=decision.gate_id,
        verdict=decision.verdict.value,
        reason=decision.reason,
        severity=decision.severity.value,
    )


def verdict_out(report: RunGateReport) -> RunVerdictOut:
    return RunVerdictOut(
        run_id=report.run_id,
        verdict=report.verdict.value,
        decisions=[decision_out(d) for d in report.decisions],
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


__all__ = ["decision_out", "verdict_out"]
