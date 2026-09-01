"""Deterministic evaluator plugins: exact match, schema validity, latency budget."""

import json

import pytest

from aegis.domain import (
    ExecutionOutcome,
    ExecutionRecord,
    TargetVersion,
    TokenUsage,
)
from aegis.domain.time import FrozenClock
from aegis.evaluation.plugins import (
    ExactMatchEvaluator,
    LatencyEvaluator,
    SchemaEvaluator,
    get_evaluator,
    list_evaluators,
)

pytestmark = pytest.mark.unit


def _execution(clock, output="hello world", latency_ms=10.0, trace="trace/1") -> ExecutionRecord:
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
            output=output,
            latency_ms=latency_ms,
            tokens=TokenUsage(input_tokens=3, output_tokens=5),
            trace_artifact_id=trace,
        ),
    )


def _test_case(clock, expected, **metadata) -> tuple:
    from aegis.domain import TestCase

    return (
        "tc:1",
        TestCase(
            id="tc:1",
            dataset_version_id="dsv:1",
            index=0,
            input="q",
            expected=expected,
            metadata=metadata,
        ),
    )


def _evidence(execution: ExecutionRecord):
    from aegis.domain import EvidenceReference

    return (
        EvidenceReference(
            execution_id=execution.id,
            dataset_case_id="tc:1",
            trace_artifact_id=execution.outcome.trace_artifact_id,
        ),
    )


def _target(clock, target_id="tvr:1") -> TargetVersion:
    return TargetVersion(
        id=target_id,
        target_id="tgt:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        config={},
        created_at=clock.now(),
    )


def test_exact_match_is_case_and_whitespace_insensitive() -> None:
    clock = FrozenClock()
    evaluator = ExactMatchEvaluator()
    ex = _execution(clock, output="  HELLO  WORLD ")
    _tc_id, tc = _test_case(clock, expected="hello world")
    results = evaluator.evaluate(clock, ex, tc, _evidence(ex)[0], mode="exact")
    assert results[0].score == 1.0
    assert results[0].evidence[0].execution_id == ex.id


def test_exact_match_detects_mismatch() -> None:
    clock = FrozenClock()
    evaluator = ExactMatchEvaluator()
    ex = _execution(clock, output="nope")
    _tc_id, tc = _test_case(clock, expected="hello world")
    result = evaluator.evaluate(clock, ex, tc, _evidence(ex)[0])[0]
    assert result.score == 0.0
    assert "differs" in result.reason


def test_schema_evaluator_validates_object_shape() -> None:
    clock = FrozenClock()
    evaluator = SchemaEvaluator()
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    ex = _execution(clock, output=json.dumps({"answer": "fine"}))
    _tc_id, tc = _test_case(clock, expected=None, schema=schema)
    assert evaluator.evaluate(clock, ex, tc, _evidence(ex)[0])[0].score == 1.0
    bad = _execution(clock, output=json.dumps({"answer": 42}))
    assert evaluator.evaluate(clock, bad, tc, _evidence(bad)[0])[0].score == 0.0


def test_schema_evaluator_rejects_invalid_json() -> None:
    clock = FrozenClock()
    evaluator = SchemaEvaluator()
    schema = {"type": "object", "properties": {}}
    ex = _execution(clock, output="not-json")
    _tc_id, tc = _test_case(clock, expected=None, schema=schema)
    assert evaluator.evaluate(clock, ex, tc, _evidence(ex)[0])[0].score == 0.0


def test_latency_evaluator_budget() -> None:
    clock = FrozenClock()
    evaluator = LatencyEvaluator()
    fast = _execution(clock, latency_ms=80.0)
    _tc_id, tc = _test_case(clock, expected=None, latency_budget_ms=100.0)
    assert evaluator.evaluate(clock, fast, tc, _evidence(fast)[0])[0].score == 1.0
    slow = _execution(clock, latency_ms=150.0)
    result = evaluator.evaluate(clock, slow, tc, _evidence(slow)[0])[0]
    assert result.score < 1.0
    assert result.raw_value == 150.0


def test_registry_exposes_versioned_plugins() -> None:
    identities = {plugin.spec().identity for plugin in list_evaluators()}
    assert "aegis/deterministic/exact_match" in identities
    assert get_evaluator("aegis/deterministic/exact_match").version == "1.0.0"
    with pytest.raises(KeyError):
        get_evaluator("aegis/deterministic/nope")


def test_plugin_spec_always_carries_identity_and_version() -> None:
    for plugin in list_evaluators():
        spec = plugin.spec()
        assert spec.identity
        assert spec.version
        assert spec.metrics
