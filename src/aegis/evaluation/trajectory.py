"""Trajectory evaluators: evidence-backed scores over agent/RAG traces.

Phase 3 evaluation depth (implementation-order.md): tool selection, recovery
from errors, and step-budget adherence are scored from the execution's preserved
trace. Every result still requires evidence (evidence-architecture.md); an
evaluator that cannot see a trace for the execution produces no result rather
than a fabricated score.
"""

from __future__ import annotations

import json
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
    """Agent step count: explicit step index when present, else tool-call count."""
    explicit = [
        int(span.attributes[AgentSpanAttributes.STEP_INDEX])
        for span in spans
        if AgentSpanAttributes.STEP_INDEX in (getattr(span, "attributes", {}) or {})
    ]
    if explicit:
        return max(explicit) + 1
    calls = tool_calls_from(spans)
    return len(calls) if calls else 0


class StepBudgetEvaluator(TrajectoryEvaluator):
    """Adherence to an agent step budget; below budget scores linearly worse."""

    identity = "aegis/trajectory/step_budget"
    version = "1.0.0"
    display_name = "Step Budget"
    metrics = ("step_budget",)
    unit = "fraction"

    def evaluate_trajectory(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        spans: Iterable[Any],
    ) -> list[MetricResult]:
        budget = float(test_case.metadata.get("step_budget") or 10.0)
        steps = step_count(spans)
        score = min(1.0, budget / steps) if steps else 1.0
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="step_budget",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=steps,
                unit=self.unit,
                reason=(
                    f"{steps} steps within {int(budget)} budget"
                    if steps <= budget
                    else f"{steps} steps over {int(budget)} budget"
                ),
            )
        ]


class ToolSelectionEvaluator(TrajectoryEvaluator):
    """Whether the expected tool (or one of several) was invoked in the trace."""

    identity = "aegis/trajectory/tool_selection"
    version = "1.0.0"
    display_name = "Tool Selection"
    metrics = ("tool_selection",)
    unit = "fraction"

    def evaluate_trajectory(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        spans: Iterable[Any],
    ) -> list[MetricResult]:
        expected = test_case.metadata.get("expected_tool")
        if expected is None:
            raise ValueError("tool_selection evaluator requires test case metadata 'expected_tool'")
        expectations = {expected} if isinstance(expected, str) else set(expected)
        used = {call.name for call in tool_calls_from(spans)}
        hit = next((name for name in expectations if name in used), None)
        score = 1.0 if hit is not None else 0.0
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="tool_selection",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=1.0 if hit is not None else 0.0,
                unit=self.unit,
                reason=(
                    f"invoked expected tool {hit!r}"
                    if hit is not None
                    else f"expected tool {sorted(expectations)[0]!r} not invoked"
                ),
            )
        ]


class RecoveryEvaluator(TrajectoryEvaluator):
    """Whether the agent recovered from a failed tool call in the same trace.

    Failing is allowed when the very next invocation of the same tool succeeds;
    an error that is never followed by a successful retry scores zero. A trace
    with no tool calls cannot be assessed and yields no result.
    """

    identity = "aegis/trajectory/recovery"
    version = "1.0.0"
    display_name = "Error Recovery"
    metrics = ("recovery",)
    unit = "fraction"

    def evaluate_trajectory(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        spans: Iterable[Any],
    ) -> list[MetricResult]:
        calls = tool_calls_from(spans)
        if not calls:
            return []
        seen_failure = False
        recovered = True
        for index, call in enumerate(calls):
            if not call.ok():
                seen_failure = True
                retried = any(
                    later.ok() and later.name == call.name for later in calls[index + 1 :]
                )
                if not retried:
                    recovered = False
                    break
        if not seen_failure:
            reason = "no tool errors observed"
            score = 1.0
        elif recovered:
            reason = "failed tool call recovered by a successful retry"
            score = 1.0
        else:
            reason = "tool error never recovered"
            score = 0.0
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="recovery",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=1.0 if recovered or not seen_failure else 0.0,
                unit=self.unit,
                reason=reason,
            )
        ]


_TRAJECTORY_REGISTRY: dict[str, TrajectoryEvaluator] = {
    e.identity: e
    for e in (StepBudgetEvaluator(), ToolSelectionEvaluator(), RecoveryEvaluator())
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
    return json.dumps(value)


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "error", "failed")
    return bool(value)


__all__ = [
    "AgentSpanAttributes",
    "RecoveryEvaluator",
    "StepBudgetEvaluator",
    "ToolCall",
    "ToolSelectionEvaluator",
    "TrajectoryEvaluator",
    "get_trajectory_evaluator",
    "is_trajectory_identity",
    "list_trajectory_evaluators",
    "step_count",
    "tool_calls_from",
]