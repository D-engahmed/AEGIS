"""Policy gates: no score without evidence; apply_gates enforces the contract."""

import pytest

from aegis.domain import EvidenceReference, EvidenceViolation, new_metric_result
from aegis.domain.time import FrozenClock
from aegis.policy.application import (
    EvidenceGate,
    PlaybackGate,
    ThresholdGate,
    apply_gates,
    evaluate_run_gates,
    override_blocked_gate,
    run_verdict,
)
from aegis.policy.models import (
    GateDecision,
    GateSeverity,
    RunGateVerdict,
    Verdict,
)

pytestmark = pytest.mark.unit


def _metric(clock, *, trace: str | None = "trace/1", input_fp: str | None = None) -> object:
    if trace is None and input_fp is None:
        input_fp = "input-fp"
    evidence = (
        EvidenceReference(
            execution_id="exe:1",
            dataset_case_id="tc:1",
            trace_artifact_id=trace,
            input_fingerprint=input_fp,
        ),
    )
    return new_metric_result(
        clock,
        run_id="run:1",
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=0.95,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0.0",
        evidence=evidence,
    )


def test_evidence_gate_passes_with_trace_link() -> None:
    clock = FrozenClock()
    decision = EvidenceGate().evaluate([_metric(clock)])
    assert decision.verdict is Verdict.PASS
    assert decision.severity is GateSeverity.INFO


def test_evidence_gate_blocks_when_only_fingerprint_no_trace() -> None:
    clock = FrozenClock()
    decision = EvidenceGate().evaluate([_metric(clock, trace=None, input_fp="fp")])
    assert decision.verdict is Verdict.ERROR
    assert decision.severity is GateSeverity.CRITICAL


def test_apply_gates_raises_evidence_violation_on_missing_trace() -> None:
    clock = FrozenClock()
    run = _run(clock)
    with pytest.raises(EvidenceViolation):
        apply_gates(run, [_metric(clock, trace=None, input_fp="fp")])


def test_apply_gates_returns_decisions_when_clean() -> None:
    clock = FrozenClock()
    decisions = apply_gates(_run(clock), [_metric(clock)])
    assert [d.verdict for d in decisions] == [Verdict.PASS for _ in decisions]


def test_playback_gate_rejects_empty_executions() -> None:
    clock = FrozenClock()
    run = _run(clock, executions=("",))
    decision = PlaybackGate().evaluate(run)
    assert decision.verdict is Verdict.FAIL


def _run(clock, executions: tuple = ()):
    from aegis.domain.execution import Run

    return Run(
        id="run:1",
        organization_id="org:1",
        project_id="prj:1",
        experiment_id="exp:1",
        snapshot=object(),
        created_by="alice",
        created_at=clock.now(),
        executions=executions,
    )


def _metric_with(clock, *, score=0.95) -> object:
    evidence = (
        EvidenceReference(
            execution_id="exe:1",
            dataset_case_id="tc:1",
            trace_artifact_id="trace/1",
        ),
    )
    return new_metric_result(
        clock,
        run_id="run:1",
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=score,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0.0",
        evidence=evidence,
    )


def test_run_verdict_aggregation() -> None:
    pass_d = GateDecision("g/pass", Verdict.PASS, "ok", GateSeverity.INFO)
    warn_d = GateDecision("g/warn", Verdict.WARN, "careful", GateSeverity.MEDIUM)
    block_d = GateDecision("g/block", Verdict.FAIL, "bad", GateSeverity.HIGH)
    assert run_verdict([pass_d]) is RunGateVerdict.PASS
    assert run_verdict([pass_d, warn_d]) is RunGateVerdict.WARN
    assert run_verdict([pass_d, block_d]) is RunGateVerdict.BLOCK


def test_threshold_gate_blocks_below_min() -> None:
    clock = FrozenClock()
    gate = ThresholdGate("dim/latency", "exact_match", min_value=0.9)
    decision = gate.evaluate([_metric_with(clock, score=0.5)])
    assert decision.verdict is Verdict.FAIL
    assert decision.severity is GateSeverity.HIGH

    healthy = ThresholdGate("dim/quality", "exact_match", min_value=0.9).evaluate(
        [_metric_with(clock, score=0.95)]
    )
    assert healthy.verdict is Verdict.PASS


def test_threshold_gate_requires_a_bound() -> None:
    with pytest.raises(ValueError):
        ThresholdGate("dim/none", "exact_match")


def test_evaluate_run_gates_reports_block_without_raising() -> None:
    clock = FrozenClock()
    run = _run(clock)
    report = evaluate_run_gates(run, [_metric(clock, trace=None, input_fp="fp")])
    assert report.verdict is RunGateVerdict.BLOCK
    assert report.is_blocked


def test_override_blocked_gate_records_override() -> None:
    clock = FrozenClock()
    run = _run(clock)
    report = evaluate_run_gates(run, [_metric(clock, trace=None, input_fp="fp")])
    overridden = override_blocked_gate(report, "alice", "manual review", clock.now())
    assert not overridden.is_blocked
    assert overridden.override is not None
    assert overridden.override.overridden_by == "alice"
    assert "policy/evidence-gate" in overridden.override.gate_ids


def test_override_refuses_non_blocked_report() -> None:
    clock = FrozenClock()
    run = _run(clock)
    report = evaluate_run_gates(run, [_metric(clock)])
    with pytest.raises(ValueError):
        override_blocked_gate(report, "alice", "why", clock.now())


def test_run_gate_service_evaluate_and_override() -> None:
    from aegis.application.run_gates import RunGateService
    from aegis.infrastructure.memory import MemoryRunGateStore

    clock = FrozenClock()
    service = RunGateService(MemoryRunGateStore(), clock)
    run = _run(clock)
    report = service.evaluate(run, [_metric(clock, trace=None, input_fp="fp")])
    assert service.report(run.id).verdict is RunGateVerdict.BLOCK
    updated = service.override(report, "owner:alice", "reviewed manually")
    assert not updated.is_blocked
    assert service.report(run.id).override is not None


def test_run_gate_service_requires_override_reason() -> None:
    from aegis.application.run_gates import RunGateService
    from aegis.domain import ValidationFailed
    from aegis.infrastructure.memory import MemoryRunGateStore

    clock = FrozenClock()
    service = RunGateService(MemoryRunGateStore(), clock)
    run = _run(clock)
    report = service.evaluate(run, [_metric(clock, trace=None, input_fp="fp")])
    with pytest.raises(ValidationFailed):
        service.override(report, "alice", "   ")
