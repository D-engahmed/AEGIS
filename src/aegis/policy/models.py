"""Ratings and gates: a gate classifies an execution verdict, the policy layer
decides what that verdict means for the experiment (PASS/WARN/BLOCK).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


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


class RunGateVerdict(enum.StrEnum):
    """The policy decision for a whole run: pass, warn, or block."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


class GateDecision:
    """The evaluable result of a gate: verdict + reason + severity."""

    def __init__(self, gate_id: str, verdict: Verdict, reason: str, severity: GateSeverity) -> None:
        self.gate_id = gate_id
        self.verdict = verdict
        self.reason = reason
        self.severity = severity


@dataclass(frozen=True)
class GateOverride:
    """Authorization to proceed past a blocked run, recorded auditably."""

    run_id: str
    overridden_by: str
    reason: str
    overridden_at: datetime
    gate_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunGateReport:
    """The persisted gate outcome for a run, with its optional override."""

    run_id: str
    verdict: RunGateVerdict
    decisions: tuple[GateDecision, ...]
    evaluated_at: datetime
    override: GateOverride | None = None

    @property
    def is_blocked(self) -> bool:
        """True while a blocking decision stands without an override."""
        return self.verdict is RunGateVerdict.BLOCK and self.override is None


__all__ = [
    "GateDecision",
    "GateOverride",
    "GateSeverity",
    "RunGateReport",
    "RunGateVerdict",
    "Verdict",
]
