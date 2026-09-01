"""Policy application: replay and evidence gates over metric results.

Implements layer 08 (Policy & Gates): a gate evaluates the metrics of an
execution, classifies the outcome, and emits PASS/WARN/BLOCK. BLOCK prevents a
score from being committed without evidence.
"""

from __future__ import annotations

from aegis.domain import MetricResult, Run
from aegis.domain.results import EvidenceViolation
from aegis.policy.models import GateDecision, GateSeverity, Verdict


class EvidenceGate:
    """ "No score without evidence": rejects results lacking trace/evidence links."""

    def __init__(self) -> None:
        self.gate_id = "policy/evidence-gate"

    def evaluate(self, results: list[MetricResult]) -> GateDecision:
        missing = [
            (r.id, r.metric_name)
            for r in results
            if not any(ev.trace_artifact_id for ev in r.evidence)
        ]
        if missing:
            return GateDecision(
                self.gate_id,
                Verdict.ERROR,
                f"{len(missing)} score(s) without trace evidence: {missing[:3]}",
                GateSeverity.CRITICAL,
            )
        return GateDecision(
            self.gate_id,
            Verdict.PASS,
            "all scores reference execution evidence",
            GateSeverity.INFO,
        )


class PlaybackGate:
    """Rejects runs whose expected values are missing (test-case contract)."""

    def __init__(self) -> None:
        self.gate_id = "policy/playback-gate"

    def evaluate(self, run: Run) -> GateDecision:
        missing = [id_ for id_ in run.executions if not id_]
        if missing:
            return GateDecision(
                self.gate_id,
                Verdict.FAIL,
                f"{len(missing)} executions missing playback data",
                GateSeverity.MEDIUM,
            )
        return GateDecision(
            self.gate_id,
            Verdict.PASS,
            "all executions carry playback data",
            GateSeverity.INFO,
        )


def apply_gates(run: Run, results: list[MetricResult]) -> list[GateDecision]:
    """Run the standard gate set; raise when evidence is missing."""
    gates = [EvidenceGate().evaluate(results), PlaybackGate().evaluate(run)]
    blocked = [d for d in gates if d.verdict is Verdict.ERROR]
    if blocked:
        raise EvidenceViolation(
            f"run {run.id!r} blocked by {', '.join(d.gate_id for d in blocked)}"
        )
    return gates


__all__ = ["EvidenceGate", "GateDecision", "GateSeverity", "PlaybackGate", "Verdict", "apply_gates"]
