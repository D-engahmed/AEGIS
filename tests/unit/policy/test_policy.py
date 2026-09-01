"""Policy gates: no score without evidence; apply_gates enforces the contract."""

import pytest

from aegis.domain import EvidenceReference, EvidenceViolation, new_metric_result
from aegis.domain.time import FrozenClock
from aegis.policy.application import EvidenceGate, PlaybackGate, apply_gates
from aegis.policy.models import GateSeverity, Verdict

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
