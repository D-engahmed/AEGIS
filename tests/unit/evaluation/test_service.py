"""Evaluation gateway: evidence-backed metrics produced from executions."""

import pytest

from aegis.application.evaluation import EvaluationService
from aegis.domain import ExecutionOutcome, ExecutionRecord, TokenUsage
from aegis.domain.time import FrozenClock
from aegis.evaluation.plugins import list_evaluators

pytestmark = pytest.mark.unit


def _execution(clock, output="hello") -> ExecutionRecord:
    return ExecutionRecord(
        id="exe:1",
        run_id="run:1",
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        status="succeeded",
        created_at=clock.now(),
        started_at=clock.now(),
        finished_at=clock.now(),
        outcome=ExecutionOutcome(
            output=output, latency_ms=5.0, tokens=TokenUsage(), trace_artifact_id="trace/1"
        ),
    )


def _target(clock):
    from aegis.domain import TargetVersion

    return TargetVersion(
        id="tvr:1",
        target_id="tgt:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        config={},
        created_at=clock.now(),
    )


def test_service_scores_with_default_evaluator() -> None:
    clock = FrozenClock()
    service = EvaluationService(clock)
    ex = _execution(clock, output="HELLO")
    target = _target(clock)
    metrics = service.evaluate(
        ex,
        "tc:1",
        target,
        ["aegis/deterministic/exact_match"],
        {"expected": "hello"},
    )
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.evaluator_identity == "aegis/deterministic/exact_match"
    assert metric.evaluator_version == "1.0.0"
    assert metric.evidence[0].trace_artifact_id == "trace/1"
    assert metric.run_id == ex.run_id


def test_service_runs_all_selected_evaluators() -> None:
    clock = FrozenClock()
    service = EvaluationService(clock)
    ex = _execution(clock, output='{"answer": "hi"}')
    target = _target(clock)
    identities = list_evaluators()
    metrics = service.evaluate(
        ex,
        "tc:1",
        target,
        [p.spec().identity for p in identities[:2]],
        {
            "expected": '{"answer": "hi"}',
            "schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        },
    )
    assert {m.metric_name for m in metrics} == {"exact_match", "schema_validity"}


def test_service_returns_nothing_without_outcome() -> None:
    clock = FrozenClock()
    service = EvaluationService(clock)
    ex = ExecutionRecord(
        id="exe:2",
        run_id="run:1",
        sequence=1,
        test_case_id="tc:2",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=clock.now(),
        outcome=None,
    )
    assert service.evaluate(ex, "tc:2", _target(clock), [], {}) == []


def test_service_skips_trajectory_evaluators_in_output_path() -> None:
    clock = FrozenClock()
    service = EvaluationService(clock)
    ex = _execution(clock, output="hello")
    metrics = service.evaluate(
        ex,
        "tc:1",
        _target(clock),
        ["aegis/trajectory/step_budget", "aegis/trajectory/tool_selection"],
        {},
    )
    assert metrics == []  # reserved for the trajectory pass


def test_service_evaluate_trajectory_scores_preserved_spans() -> None:
    from aegis.domain import Run
    from aegis.domain.datasets import TestCase
    from aegis.domain.execution import ExperimentSnapshot
    from aegis.domain.results import EvidenceReference
    from aegis.observability.models import SpanAttributes, TraceRecord

    clock = FrozenClock()
    now = clock.now()
    span_kwargs = {SpanAttributes.EXECUTION_ID: "exec:1"}
    execution = ExecutionRecord(
        id="exec:1",
        run_id="run:1",
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        created_at=now,
        outcome=ExecutionOutcome(
            output="answer", latency_ms=5.0, tokens=TokenUsage(), trace_artifact_id="trace/1"
        ),
        evidence_references=(
            EvidenceReference(
                execution_id="exec:1", dataset_case_id="tc:1", trace_artifact_id="trace/1"
            ),
        ),
    )
    record = TraceRecord(
        trace_id="trace/1",
        run_id="run:1",
        execution_id="exec:1",
        preserved_at=now,
        spans=(
            _tool_span(clock, "search", span_kwargs, error="1"),
            _tool_span(clock, "search", span_kwargs),
            _tool_span(clock, "calculator", span_kwargs),
        ),
    )
    service = EvaluationService(clock, trace_source=lambda _run_id: [record])
    test_case = TestCase(
        id="tc:1", dataset_version_id="dsv:1", index=0, input="q", expected="a",
        metadata={"step_budget": 5, "expected_tool": "calculator"},
    )
    run = Run(
        id="run:1",
        organization_id="org:1",
        project_id="prj:1",
        experiment_id="exp:1",
        created_by="alice",
        created_at=now,
        snapshot=ExperimentSnapshot(
            target_version_id="tvr:1",
            dataset_version_id="dsv:1",
            evaluator_version_ids=(
                "aegis/trajectory/step_budget",
                "aegis/trajectory/recovery",
            ),
            settings={},
        ),
    )

    results = service.evaluate_trajectory(run, [execution], [test_case])
    assert len(results) == 2
    assert {r.metric_name for r in results} == {"step_budget", "recovery"}
    step = next(r for r in results if r.metric_name == "step_budget")
    assert step.evaluator_identity == "aegis/trajectory/step_budget"
    assert step.raw_value == 3
    recovery = next(r for r in results if r.metric_name == "recovery")
    assert recovery.score == 1.0
    assert recovery.evidence[0].dataset_case_id == "tc:1"

    # no trace source -> no trajectory results
    results = EvaluationService(clock).evaluate_trajectory(run, [execution], [test_case])
    assert results == []


def _tool_span(clock, tool: str, base: dict, error: str | None = None) -> object:
    from aegis.evaluation.trajectory import AgentSpanAttributes
    from aegis.observability.models import SpanData, SpanStatusCode

    attributes = {**base, AgentSpanAttributes.TOOL_NAME: tool}
    if error is not None:
        attributes[AgentSpanAttributes.TOOL_ERROR] = error
    return SpanData(
        span_id="s",
        name="tool.call",
        trace_id="trace/1",
        parent_span_id=None,
        start_time=clock.now(),
        end_time=clock.now(),
        status=SpanStatusCode.OK,
        attributes=attributes,
    )
