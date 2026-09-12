"""Trajectory evaluators: step budget, tool selection, error recovery."""

from datetime import UTC, datetime

import pytest

from aegis.domain.datasets import TestCase as EvalTestCase
from aegis.domain.execution import ExecutionOutcome, ExecutionRecord, ExecutionStatus
from aegis.domain.results import EvidenceReference
from aegis.domain.time import FrozenClock
from aegis.evaluation.trajectory import (
    AgentSpanAttributes,
    RecoveryEvaluator,
    StepBudgetEvaluator,
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
        id="exec:1",
        run_id="run:1",
        sequence=0,
        test_case_id=test_case_id,
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        outcome=ExecutionOutcome(output="answer", latency_ms=1.0),
        status=ExecutionStatus.SUCCEEDED,
    )


def _evidence() -> EvidenceReference:
    return EvidenceReference(
        execution_id="exec:1",
        dataset_case_id="case:1",
        trace_artifact_id="trace/exec:1",
    )


def _test_case(**metadata) -> EvalTestCase:
    return EvalTestCase(
        id="case:1",
        dataset_version_id="dsv:1",
        index=0,
        input="q",
        expected="a",
        metadata=metadata,
    )


def _span(name: str, **attributes) -> SpanData:
    return SpanData(
        span_id="s",
        name=name,
        trace_id="trace:1",
        parent_span_id=None,
        start_time=CLOCK.now(),
        end_time=CLOCK.now(),
        status=SpanStatusCode.OK,
        attributes={**attributes, "aegis.execution.id": "exec:1"},
    )


def tool_span(tool: str, **attributes) -> SpanData:
    return _span("tool.call", **{AgentSpanAttributes.TOOL_NAME: tool, **attributes})


def test_tool_calls_from_lifts_only_tool_spans() -> None:
    spans = [tool_span("search"), _span("model.call"), tool_span("search")]
    calls = tool_calls_from(spans)
    assert [call.name for call in calls] == ["search", "search"]
    assert all(not call.error for call in calls)


def test_step_count_uses_explicit_index_when_present() -> None:
    spans = [
        tool_span("a", **{AgentSpanAttributes.STEP_INDEX: 0}),
        tool_span("b", **{AgentSpanAttributes.STEP_INDEX: 1}),
        tool_span("c", **{AgentSpanAttributes.STEP_INDEX: 1}),
    ]
    assert step_count(spans) == 2


def test_step_count_falls_back_to_tool_call_count() -> None:
    assert step_count([tool_span("a"), tool_span("b"), tool_span("c")]) == 3
    assert step_count([]) == 0


def test_step_budget_scores_within_and_over_budget() -> None:
    evaluator = StepBudgetEvaluator()
    assert is_trajectory_identity(evaluator.identity)

    within = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(step_budget=5),
        _evidence(),
        [tool_span("a") for _ in range(3)],
    )[0]
    assert within.score == 1.0
    assert within.metric_name == "step_budget"
    assert within.raw_value == 3
    assert "within" in (within.reason or "")

    over = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(step_budget=2),
        _evidence(),
        [tool_span("a") for _ in range(4)],
    )[0]
    assert over.score == pytest.approx(0.5)
    assert over.raw_value == 4
    assert "over" in (over.reason or "")


def test_tool_selection_requires_expected_tool_metadata() -> None:
    evaluator = ToolSelectionEvaluator()
    with pytest.raises(ValueError):
        evaluator.evaluate_trajectory(
            CLOCK, _execution(), _test_case(), _evidence(), [tool_span("search")]
        )


def test_tool_selection_scores_hit_and_miss() -> None:
    evaluator = ToolSelectionEvaluator()
    hit = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(expected_tool="calculator"),
        _evidence(),
        [tool_span("search"), tool_span("calculator")],
    )[0]
    assert hit.score == 1.0
    assert hit.raw_value == 1.0

    miss = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(expected_tool="database.query"),
        _evidence(),
        [tool_span("search")],
    )[0]
    assert miss.score == 0.0
    assert miss.raw_value == 0.0


def test_tool_selection_accepts_any_of_several_expected_tools() -> None:
    evaluator = ToolSelectionEvaluator()
    result = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(expected_tool=["database.query", "document.search"]),
        _evidence(),
        [tool_span("document.search")],
    )[0]
    assert result.score == 1.0


def test_recovery_returns_no_result_without_tool_calls() -> None:
    evaluator = RecoveryEvaluator()
    assert (
        evaluator.evaluate_trajectory(
            CLOCK, _execution(), _test_case(), _evidence(), [_span("model.call")]
        )
        == []
    )


def test_recovery_scores_error_then_retry_and_unrecovered() -> None:
    evaluator = RecoveryEvaluator()
    recovered = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(),
        _evidence(),
        [
            tool_span("search", **{AgentSpanAttributes.TOOL_ERROR: "1"}),
            tool_span("search"),
        ],
    )[0]
    assert recovered.score == 1.0
    assert "recovered" in (recovered.reason or "")

    stuck = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(),
        _evidence(),
        [
            tool_span("search", **{AgentSpanAttributes.TOOL_ERROR: "1"}),
            tool_span("calculator"),
        ],
    )[0]
    assert stuck.score == 0.0
    assert "never recovered" in (stuck.reason or "")


def test_recovery_passes_when_no_errors_found() -> None:
    evaluator = RecoveryEvaluator()
    result = evaluator.evaluate_trajectory(
        CLOCK,
        _execution(),
        _test_case(),
        _evidence(),
        [tool_span("search"), tool_span("calculator")],
    )[0]
    assert result.score == 1.0
    assert "no tool errors" in (result.reason or "")


def test_registry_exposes_trajectory_evaluators() -> None:
    identities = {e.identity for e in list_trajectory_evaluators()}
    assert identities == {
        "aegis/trajectory/step_budget",
        "aegis/trajectory/tool_selection",
        "aegis/trajectory/recovery",
    }
    assert get_trajectory_evaluator("aegis/trajectory/recovery").identity == (
        "aegis/trajectory/recovery"
    )
    with pytest.raises(KeyError):
        get_trajectory_evaluator("aegis/not/a/thing")