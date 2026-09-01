"""Ratings and gates: a gate classifies an execution verdict, the policy layer
decides what that verdict means for the experiment (PASS/WARN/BLOCK).
"""

from __future__ import annotations

import enum


class GateSeverity(enum.StrEnum):
    """Severity of a single gate check."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def blocks(self) -> bool:
        return self in (GateSeverity.HIGH, GateSeverity.CRITICAL)


class Verdict(enum.StrEnum):
    """Evidence-supported verdict for one execution."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"


class GateDecision:
    """The evaluable result of a gate: verdict + reason + severity."""

    def __init__(self, gate_id: str, verdict: Verdict, reason: str, severity: GateSeverity) -> None:
        self.gate_id = gate_id
        self.verdict = verdict
        self.reason = reason
        self.severity = severity


__all__ = ["GateDecision", "GateSeverity", "Verdict"]
