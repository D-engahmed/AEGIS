"""Policy application: replay and evidence gates over metric results.

Implements layer 08 (Policy & Gates): a gate evaluates the metrics of an
execution, classifies the outcome, and emits PASS/WARN/RESULT. BLOCK prevents a
score from being committed without evidence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from typing import Protocol

from aegis.domain import MetricResult, Run
from aegis.domain.results import EvidenceViolation
from aegis.policy.models import (
    GateDecision,
    GateOverride,
    GateSeverity,
    RunGateReport,
    RunGateVerdict,
    Verdict,
)


class Gate(Protocol):
    """A single gate check over a run's metric results."""

    gate_id: str

    def evaluate(self, results: list[MetricResult]) -> GateDecision: ...


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


class ThresholdGate:
    """Dimensions gate: blocks when a metric drifts past a bound.

    Non-compensatory by construction: a failing dimension yields a blocking
    decision regardless of how well other metrics perform (grilling.md severity
    model, deployment-strategy.md).
    """

    def __init__(
        self,
        gate_id: str,
        metric_name: str,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        severity: GateSeverity = GateSeverity.HIGH,
    ) -> None:
        if min_value is None and max_value is None:
            raise ValueError("threshold gate requires at least one bound")
        self.gate_id = gate_id
        self._metric_name = metric_name
        self._min_value = min_value
        self._max_value = max_value
        self._severity = severity

    def evaluate(self, results: list[MetricResult]) -> GateDecision:
        scores = [
            r.score for r in results if r.metric_name == self._metric_name and r.score is not None
        ]
        if not scores:
            return GateDecision(
                self.gate_id,
                Verdict.WARN,
                f"no results measured for metric {self._metric_name!r}",
                GateSeverity.LOW,
            )
        if self._min_value is not None and min(scores) < self._min_value:
            return GateDecision(
                self.gate_id,
                Verdict.FAIL,
                f"metric {self._metric_name!r} below {self._min_value} (worst {min(scores):.4f})",
                self._severity,
            )
        if self._max_value is not None and max(scores) > self._max_value:
            return GateDecision(
                self.gate_id,
                Verdict.FAIL,
                f"metric {self._metric_name!r} above {self._max_value} (worst {max(scores):.4f})",
                self._severity,
            )
        return GateDecision(
            self.gate_id,
            Verdict.PASS,
            f"metric {self._metric_name!r} within bounds",
            GateSeverity.INFO,
        )


def run_verdict(decisions: Iterable[GateDecision]) -> RunGateVerdict:
    """Aggregate gate decisions to a single run verdict.

    Blocking severity is non-compensatory: any HIGH/CRITICAL failure blocks the
    run no matter how many dimensions pass.
    """
    listed = tuple(decisions)
    blocked = [d for d in listed if d.severity.blocks]
    if blocked:
        return RunGateVerdict.BLOCK
    if any(d.verdict is not Verdict.PASS for d in listed):
        return RunGateVerdict.WARN
    return RunGateVerdict.PASS


def evaluate_run_gates(
    run: Run,
    results: list[MetricResult],
    *,
    gates: Iterable[Gate] = (),
) -> RunGateReport:
    """Evaluate the run's gate set and produce a persisted report.

    Unlike apply_gates (which raises for missing evidence), this records every
    decision; an evidence failure becomes a blocking report.
    """
    standard: list[GateDecision] = [EvidenceGate().evaluate(results), PlaybackGate().evaluate(run)]
    extra: list[GateDecision] = [gate.evaluate(results) for gate in gates]
    decisions = tuple(standard) + tuple(extra)
    return RunGateReport(
        run_id=run.id,
        verdict=run_verdict(decisions),
        decisions=decisions,
        evaluated_at=run.finished_at or run.created_at,
    )


def override_blocked_gate(
    report: RunGateReport,
    overridden_by: str,
    reason: str,
    at: datetime,
) -> RunGateReport:
    """Authorize proceeding past a blocked run; refuses non-blocked reports."""
    if report.verdict is not RunGateVerdict.BLOCK:
        raise ValueError(f"run {report.run_id!r} is not blocked; nothing to override")
    blocking = tuple(d.gate_id for d in report.decisions if d.severity.blocks)
    return replace(
        report,
        override=GateOverride(
            run_id=report.run_id,
            overridden_by=overridden_by,
            reason=reason,
            overridden_at=at,
            gate_ids=blocking,
        ),
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


__all__ = [
    "EvidenceGate",
    "GateDecision",
    "GateOverride",
    "GateSeverity",
    "PlaybackGate",
    "RunGateVerdict",
    "ThresholdGate",
    "Verdict",
    "apply_gates",
    "evaluate_run_gates",
    "override_blocked_gate",
    "run_verdict",
]
