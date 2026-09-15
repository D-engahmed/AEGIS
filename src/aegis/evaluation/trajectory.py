"""Trajectory evaluators: evidence-backed scores over agent/RAG traces.

The trajectory layer evaluates agent behaviour rather than only final output.
All evaluators are deterministic, versioned, and require an evidence reference.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from aegis.domain.datasets import TestCase
from aegis.domain.execution import ExecutionRecord
from aegis.domain.results import EvidenceReference, MetricResult, new_metric_result
from aegis.domain.time import Clock


class AgentSpanAttributes:
    """OpenTelemetry-compatible attribute keys used to read a trajectory."""

    TOOL_NAME = "aegis.tool.name"
    TOOL_INPUT = "aegis.tool.input"
    TOOL_RESULT = "aegis.tool.result"
    TOOL_ERROR = "aegis.tool.error"
    STEP_INDEX = "aegis.agent.step"
    RECOVERY_ATTEMPT = "aegis.agent.recovery"
    LOOP_DETECTED = "aegis.agent.loop"


@dataclass(frozen=True)
class ToolCall:
    """A normalized tool invocation lifted from a trace span."""

    name: str
    input: str | None = None
    result: str | None = None
    error: bool = False

    def ok(self) -> bool:
        return not self.error


class TrajectoryEvaluator:
    """Base class: scores a trajectory, never the raw output string."""

    identity = "aegis/trajectory/base"
    version = "0.0.0"
    display_name = "Trajectory"
    metrics: tuple[str, ...] = ()
    severity: str = "info"
    unit: str | None = None
    requires_trace = True

    def evaluate_trajectory(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        spans: Iterable[Any],
    ) -> list[MetricResult]:
        raise NotImplementedError


def tool_calls_from(spans: Iterable[Any]) -> list[ToolCall]:
    """Lift tool-call spans into a normalized, ordered trajectory."""
    calls: list[ToolCall] = []
    for span in spans:
        attributes = getattr(span, "attributes", {}) or {}
        name = attributes.get(AgentSpanAttributes.TOOL_NAME)
        if name is None:
            continue
        calls.append(
            ToolCall(
                name=str(name),
                input=_as_json(attributes.get(AgentSpanAttributes.TOOL_INPUT)),
                result=_as_json(attributes.get(AgentSpanAttributes.TOOL_RESULT)),
                error=_truthy(attributes.get(AgentSpanAttributes.TOOL_ERROR)),
            )
        )
    return calls


def step_count(spans: Iterable[Any]) -> int:
    """Agent step count using explicit zero-based indices when available."""
    span_list = list(spans)
    explicit = [
        int(span.attributes[AgentSpanAttributes.STEP_INDEX])
        for span in span_list
        if AgentSpanAttributes.STEP_INDEX in (getattr(span, "attributes", {}) or {})
    ]
    if explicit:
        if min(explicit) < 0:
            raise ValueError("agent step index must be non-negative")
        return max(explicit) + 1
    calls = tool_calls_from(span_list)
    return len(calls)


def _metric(
    clock: Clock,
    execution: ExecutionRecord,
    test_case: TestCase,
    evidence: EvidenceReference,
    *,
    metric_name: str,
    score: float,
    identity: str,
    version: str,
    raw_value: object,
    reason: str,
    unit: str | None = "fraction",
) -> MetricResult:
    return new_metric_result(
        clock,
        run_id=execution.run_id,
        execution_id=execution.id,
        test_case_id=test_case.id,
        metric_name=metric_name,
        score=max(0.0, min(1.0, score)),
        evaluator_identity=identity,
        evaluator_version=version,
        evidence=(evidence,),
        raw_value=raw_value,
        unit=unit,
        reason=reason,
    )


class StepBudgetEvaluator(TrajectoryEvaluator):
    """Score adherence to an agent step budget."""

    identity = "aegis/trajectory/step_budget"
    version = "1.1.0"
    display_name = "Step Budget"
    metrics = ("step_budget",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        budget = float(test_case.metadata.get("step_budget") or 10.0)
        if budget <= 0:
            raise ValueError("step_budget must be greater than zero")
        steps = step_count(spans)
        score = min(1.0, budget / steps) if steps else 1.0
        return [
            _metric(
                clock, execution, test_case, evidence,
                metric_name="step_budget", score=score, identity=self.identity,
                version=self.version, raw_value=steps,
                reason=(f"{steps} steps within {int(budget)} budget"
                         if steps <= budget else f"{steps} steps over {int(budget)} budget"),
            )
        ]


class ToolSelectionEvaluator(TrajectoryEvaluator):
    """Score whether at least one expected tool was selected."""

    identity = "aegis/trajectory/tool_selection"
    version = "1.0.0"
    display_name = "Tool Selection"
    metrics = ("tool_selection",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        expected = test_case.metadata.get("expected_tool")
        if expected is None:
            raise ValueError("tool_selection evaluator requires test case metadata 'expected_tool'")
        expectations = {expected} if isinstance(expected, str) else {str(v) for v in expected}
        if not expectations:
            raise ValueError("expected_tool must contain at least one tool")
        used = {call.name for call in tool_calls_from(spans)}
        hit = next((name for name in sorted(expectations) if name in used), None)
        return [
            _metric(
                clock, execution, test_case, evidence,
                metric_name="tool_selection", score=1.0 if hit else 0.0,
                identity=self.identity, version=self.version,
                raw_value=1.0 if hit else 0.0,
                reason=(f"invoked expected tool {hit!r}" if hit
                         else f"expected tool {sorted(expectations)[0]!r} not invoked"),
            )
        ]


class RecoveryEvaluator(TrajectoryEvaluator):
    """Score whether failed tool calls are eventually recovered."""

    identity = "aegis/trajectory/recovery"
    version = "1.0.0"
    display_name = "Error Recovery"
    metrics = ("recovery",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        calls = tool_calls_from(spans)
        if not calls:
            return []
        failures = [i for i, call in enumerate(calls) if call.error]
        if not failures:
            score, reason = 1.0, "no tool errors observed"
        else:
            recovered = sum(
                any(later.ok() and later.name == calls[i].name for later in calls[i + 1:])
                for i in failures
            )
            score = recovered / len(failures)
            reason = f"recovered {recovered}/{len(failures)} failed tool calls"
        return [_metric(clock, execution, test_case, evidence,
                        metric_name="recovery", score=score, identity=self.identity,
                        version=self.version, raw_value=score, reason=reason)]


class ToolPrecisionEvaluator(TrajectoryEvaluator):
    """Measure unnecessary tool calls against an allowed tool set."""

    identity = "aegis/trajectory/tool_precision"
    version = "1.0.0"
    display_name = "Tool Precision"
    metrics = ("tool_precision",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        allowed = test_case.metadata.get("allowed_tools")
        if allowed is None:
            raise ValueError("tool_precision evaluator requires 'allowed_tools'")
        allowed_set = {allowed} if isinstance(allowed, str) else {str(v) for v in allowed}
        calls = tool_calls_from(spans)
        if not calls:
            return [_metric(clock, execution, test_case, evidence,
                            metric_name="tool_precision", score=1.0,
                            identity=self.identity, version=self.version,
                            raw_value=1.0, reason="no tool calls observed")]
        valid = sum(call.name in allowed_set for call in calls)
        score = valid / len(calls)
        return [_metric(clock, execution, test_case, evidence,
                        metric_name="tool_precision", score=score,
                        identity=self.identity, version=self.version,
                        raw_value=score,
                        reason=f"{valid}/{len(calls)} tool calls were allowed")]


class ToolRecallEvaluator(TrajectoryEvaluator):
    """Measure whether all required tools were invoked at least once."""

    identity = "aegis/trajectory/tool_recall"
    version = "1.0.0"
    display_name = "Tool Recall"
    metrics = ("tool_recall",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        required = test_case.metadata.get("required_tools")
        if required is None:
            raise ValueError("tool_recall evaluator requires 'required_tools'")
        required_set = {required} if isinstance(required, str) else {str(v) for v in required}
        if not required_set:
            raise ValueError("required_tools must contain at least one tool")
        used = {call.name for call in tool_calls_from(spans)}
        hits = len(required_set & used)
        score = hits / len(required_set)
        return [_metric(clock, execution, test_case, evidence,
                        metric_name="tool_recall", score=score,
                        identity=self.identity, version=self.version,
                        raw_value=score,
                        reason=f"invoked {hits}/{len(required_set)} required tools")]


class LoopDetectionEvaluator(TrajectoryEvaluator):
    """Penalize repeated tool-call sequences that indicate agent loops."""

    identity = "aegis/trajectory/loop_detection"
    version = "1.0.0"
    display_name = "Loop Detection"
    metrics = ("loop_detection",)
    unit = "fraction"

    def evaluate_trajectory(self, clock, execution, test_case, evidence, spans):
        calls = tool_calls_from(spans)
        threshold = int(test_case.metadata.get("loop_threshold") or 3)
        if threshold < 2:
            raise ValueError("loop_threshold must be at least 2")
        counts = Counter(call.name for call in calls)
        offenders = sorted(name for name, count in counts.items() if count >= threshold)
        score = 0.0 if offenders else 1.0
        reason = (f"repeated tool calls detected: {', '.join(offenders)}"
                  if offenders else "no repeated-tool loop detected")
        return [_metric(clock, execution, test_case, evidence,
                        metric_name="loop_detection", score=score,
                        identity=self.identity, version=self.version,
                        raw_value=offenders, reason=reason)]


_TRAJECTORY_REGISTRY: dict[str, TrajectoryEvaluator] = {
    e.identity: e
    for e in (
        StepBudgetEvaluator(),
        ToolSelectionEvaluator(),
        RecoveryEvaluator(),
        ToolPrecisionEvaluator(),
        ToolRecallEvaluator(),
        LoopDetectionEvaluator(),
    )
}

_TRAJECTORY_IDENTITIES = set(_TRAJECTORY_REGISTRY)


def is_trajectory_identity(identity: str) -> bool:
    return identity in _TRAJECTORY_IDENTITIES


def get_trajectory_evaluator(identity: str) -> TrajectoryEvaluator:
    if identity not in _TRAJECTORY_REGISTRY:
        raise KeyError(f"unknown trajectory evaluator {identity!r}")
    return _TRAJECTORY_REGISTRY[identity]


def list_trajectory_evaluators() -> list[TrajectoryEvaluator]:
    return list(_TRAJECTORY_REGISTRY.values())


def _as_json(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "error", "failed")
    return bool(value)


__all__ = [
    "AgentSpanAttributes",
    "LoopDetectionEvaluator",
    "RecoveryEvaluator",
    "StepBudgetEvaluator",
    "ToolCall",
    "ToolPrecisionEvaluator",
    "ToolRecallEvaluator",
    "ToolSelectionEvaluator",
    "TrajectoryEvaluator",
    "get_trajectory_evaluator",
    "is_trajectory_identity",
    "list_trajectory_evaluators",
    "step_count",
    "tool_calls_from",
]
