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
