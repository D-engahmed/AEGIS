"""Trajectory evaluators: budgets, selection, recovery, precision, recall, loops."""

from datetime import UTC, datetime

import pytest

from aegis.domain.datasets import TestCase as EvalTestCase
from aegis.domain.execution import ExecutionOutcome, ExecutionRecord, ExecutionStatus
from aegis.domain.results import EvidenceReference
from aegis.domain.time import FrozenClock
from aegis.evaluation.trajectory import (
    AgentSpanAttributes,
    LoopDetectionEvaluator,
    RecoveryEvaluator,
    StepBudgetEvaluator,
    ToolPrecisionEvaluator,
    ToolRecallEvaluator,
    ToolSelectionEvaluator,
    get_trajectory_evaluator,
    is_trajectory_identity,
    list_trajectory_evaluators,
    step_count,
    tool_calls_from,
)
from aegis.observability.models import SpanData, SpanStatusCode

pytestmark = pytest.mark.unit

CLOCK = FrozenClock(datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC))


def _execution(test_case_id: str = "case:1") -> ExecutionRecord:
    return ExecutionRecord(
        id="exec:1", run_id="run:1", sequence=0, test_case_id=test_case_id,
        target_version_id="tvr:1", dataset_version_id="dsv:1",
        outcome=ExecutionOutcome(output="answer", latency_ms=1.0),
        status=ExecutionStatus.SUCCEEDED,
    )


def _evidence() -> EvidenceReference:
    return EvidenceReference(execution_id="exec:1", dataset_case_id="case:1", trace_artifact_id="trace/exec:1")


def _test_case(**metadata) -> EvalTestCase:
    return EvalTestCase(id="case:1", dataset_version_id="dsv:1", index=0, input="q", expected="a", metadata=metadata)


def _span(name: str, **attributes) -> SpanData:
    return SpanData(span_id="s", name=name, trace_id="trace:1", parent_span_id=None,
                    start_time=CLOCK.now(), end_time=CLOCK.now(), status=SpanStatusCode.OK,
                    attributes={**attributes, "aegis.execution.id": "exec:1"})


def tool_span(tool: str, **attributes) -> SpanData:
    return _span("tool.call", **{AgentSpanAttributes.TOOL_NAME: tool, **attributes})


def test_tool_calls_from_lifts_only_tool_spans() -> None:
    calls = tool_calls_from([tool_span("search"), _span("model.call"), tool_span("search")])
    assert [call.name for call in calls] == ["search", "search"]
    assert all(not call.error for call in calls)


def test_step_count_uses_explicit_index_and_fallback() -> None:
    spans = [tool_span("a", **{AgentSpanAttributes.STEP_INDEX: 0}),
             tool_span("b", **{AgentSpanAttributes.STEP_INDEX: 1}),
             tool_span("c", **{AgentSpanAttributes.STEP_INDEX: 1})]
    assert step_count(spans) == 2
    assert step_count([tool_span("a"), tool_span("b"), tool_span("c")]) == 3
    with pytest.raises(ValueError):
        step_count([tool_span("a", **{AgentSpanAttributes.STEP_INDEX: -1})])


def test_step_budget_scores_within_and_over_budget() -> None:
    evaluator = StepBudgetEvaluator()
    within = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(step_budget=5), _evidence(), [tool_span("a") for _ in range(3)])[0]
    assert within.score == 1.0 and within.raw_value == 3
    over = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(step_budget=2), _evidence(), [tool_span("a") for _ in range(4)])[0]
    assert over.score == pytest.approx(0.5) and over.raw_value == 4
    with pytest.raises(ValueError):
        evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(step_budget=0), _evidence(), [])


def test_tool_selection_scores_hit_and_miss_and_validates_configuration() -> None:
    evaluator = ToolSelectionEvaluator()
    with pytest.raises(ValueError):
        evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(), _evidence(), [tool_span("search")])
    hit = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(expected_tool=["database.query", "document.search"]), _evidence(), [tool_span("document.search")])[0]
    assert hit.score == 1.0
    miss = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(expected_tool="database.query"), _evidence(), [tool_span("search")])[0]
    assert miss.score == 0.0


def test_recovery_scores_fraction_of_failures_recovered() -> None:
    evaluator = RecoveryEvaluator()
    result = evaluator.evaluate_trajectory(
        CLOCK, _execution(), _test_case(), _evidence(),
        [tool_span("search", **{AgentSpanAttributes.TOOL_ERROR: "1"}), tool_span("search"),
         tool_span("db", **{AgentSpanAttributes.TOOL_ERROR: "1"}), tool_span("calculator")],
    )[0]
    assert result.score == 0.5
    assert "1/2" in (result.reason or "")
    assert evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(), _evidence(), [_span("model.call")]) == []


def test_tool_precision_detects_unnecessary_calls() -> None:
    evaluator = ToolPrecisionEvaluator()
    result = evaluator.evaluate_trajectory(
        CLOCK, _execution(), _test_case(allowed_tools=["search", "calculator"]), _evidence(),
        [tool_span("search"), tool_span("database"), tool_span("calculator")],
    )[0]
    assert result.score == pytest.approx(2 / 3)


def test_tool_recall_requires_all_required_tools() -> None:
    evaluator = ToolRecallEvaluator()
    result = evaluator.evaluate_trajectory(
        CLOCK, _execution(), _test_case(required_tools=["search", "calculator", "customer_lookup"]), _evidence(),
        [tool_span("search"), tool_span("calculator")],
    )[0]
    assert result.score == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(required_tools=[]), _evidence(), [])


def test_loop_detection_flags_repeated_tool_usage() -> None:
    evaluator = LoopDetectionEvaluator()
    clean = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(loop_threshold=3), _evidence(),
                                           [tool_span("search"), tool_span("calculator")])[0]
    assert clean.score == 1.0
    loop = evaluator.evaluate_trajectory(CLOCK, _execution(), _test_case(loop_threshold=3), _evidence(),
                                         [tool_span("search"), tool_span("search"), tool_span("search")])[0]
    assert loop.score == 0.0
    assert "search" in (loop.reason or "")


def test_registry_contains_six_trajectory_evaluators() -> None:
    identities = {e.identity for e in list_trajectory_evaluators()}
    assert identities == {
        "aegis/trajectory/step_budget",
        "aegis/trajectory/tool_selection",
        "aegis/trajectory/recovery",
        "aegis/trajectory/tool_precision",
        "aegis/trajectory/tool_recall",
        "aegis/trajectory/loop_detection",
    }
    assert all(is_trajectory_identity(identity) for identity in identities)
    assert get_trajectory_evaluator("aegis/trajectory/recovery").identity == "aegis/trajectory/recovery"
    with pytest.raises(KeyError):
        get_trajectory_evaluator("aegis/not/a/thing")
