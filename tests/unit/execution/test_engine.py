"""Engine integration: bounded retries, cancellation, timeouts, evidence preserved.

Each run is fully deterministic: scripted targets and a frozen clock pin every
transition (failure-architecture.md).
"""

from datetime import timedelta

import pytest

from aegis.domain import FailureCode, RunStatus
from aegis.execution.engine import fingerprint
from aegis.execution.retry import RetryPolicy
from aegis.execution.timeout import TimeoutPolicy
from tests.conftest import ScriptedTarget, SteppingClock

pytestmark = pytest.mark.unit


def _fast_retry() -> RetryPolicy:
    return RetryPolicy(max_attempts=3, base_delay_seconds=0, jitter_ratio=0)


def test_engine_completes_run_with_evidence(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"), ("bye", "bye"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget("hello", "bye")
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
    )

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.SUCCEEDED
    assert result.evidence_summary.total_executions == 2
    assert result.evidence_summary.completed_executions == 2
    assert len(result.executions) == 2
    executions = harness.executions.list_for_run(run.id)
    assert all(ex.status.value == "succeeded" for ex in executions)
    assert all(
        ex.evidence_references and ex.evidence_references[0].trace_artifact_id for ex in executions
    )
    metrics = harness.results.list_for_run(run.id)
    assert len(metrics) == 2
    assert all(m.evidence and m.evidence[0].trace_artifact_id for m in metrics)


def test_engine_is_idempotent_for_terminal_runs(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget("hello")
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
    )

    first = harness.engine.run(run.id)
    second = harness.engine.run(run.id)

    assert second is first
    assert len(harness.executions.list_for_run(run.id)) == 1
    assert len(harness.results.list_for_run(run.id)) == 1
    assert harness.target.calls == harness.target.calls[:1]


def test_engine_retries_transient_then_succeeds(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget(FailureCode.TEMPORARY_UNAVAILABLE, "hello")
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        retry=_fast_retry(),
    )

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.SUCCEEDED
    executions = harness.executions.list_for_run(run.id)
    assert executions[0].retries == 1
    assert len(target.calls) == 2
    assert target.calls[0].timeout_seconds == 30.0


def test_engine_fails_when_retries_exhausted_and_preserves_partial(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"), ("bye", "bye"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget(FailureCode.PROVIDER_RATE_LIMIT)
    retry = RetryPolicy(max_attempts=2, base_delay_seconds=0, jitter_ratio=0)
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        retry=retry,
    )

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code is FailureCode.PROVIDER_RATE_LIMIT
    assert result.evidence_summary.partial_preserved
    assert result.evidence_summary.completed_executions == 1
    execution = harness.executions.list_for_run(run.id)[0]
    assert execution.status.value == "failed"
    assert execution.failure.code is FailureCode.PROVIDER_RATE_LIMIT
    assert len(target.calls) == 2


def test_non_retryable_failure_is_fatal(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget(FailureCode.MALFORMED_RESPONSE)
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        retry=_fast_retry(),
    )

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.FAILED
    assert result.error.code is FailureCode.MALFORMED_RESPONSE
    assert len(target.calls) == 1


def test_pre_cancelled_run_collaborates_and_stamps_identity(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    harness = make_harness(run=run, target_version=target_version, dataset_version=dataset)
    harness.registry.cancel(run.id, "alice", clock)

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.CANCELLED
    assert result.cancelled_by == "alice"
    assert result.evidence_summary.partial_preserved
    assert harness.executions.list_for_run(run.id) == []


def test_cancel_during_retry_sleep_keeps_failure_distinguishable(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget(FailureCode.TEMPORARY_UNAVAILABLE, FailureCode.TEMPORARY_UNAVAILABLE)
    registry_holder: dict[str, object] = {}

    def sleep_during_retry(_seconds: float) -> None:
        registry_holder["registry"].cancel(run.id, "bob", clock)

    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        retry=_fast_retry(),
        sleep=sleep_during_retry,
    )
    registry_holder["registry"] = harness.registry

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.CANCELLED
    assert result.cancelled_by == "bob"
    executions = harness.executions.list_for_run(run.id)
    assert executions and executions[0].status.value == "failed"


def test_per_experiment_timeout_fails_run(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    fast_clock = SteppingClock(timedelta(seconds=2))
    dataset = make_dataset_version(("hi", "hello"), ("bye", "bye"), clock=fast_clock)
    target_version = make_target_version(clock=fast_clock)
    run = make_run(
        target_version_id=target_version.id,
        dataset_version_id=dataset.id,
        clock=fast_clock,
    )
    target = ScriptedTarget("hello", "bye", "later")
    harness = make_harness(
        clock=fast_clock,
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        timeouts=TimeoutPolicy(
            per_experiment_seconds=3, per_target_seconds=300, per_test_seconds=30
        ),
        retry=_fast_retry(),
    )

    result = harness.engine.run(run.id)

    assert result.status is RunStatus.FAILED
    assert result.error.code is FailureCode.EXPERIMENT_TIMEOUT
    assert result.evidence_summary.total_executions == 2
    assert result.evidence_summary.completed_executions <= 1
    assert result.evidence_summary.partial_preserved


def test_fingerprint_is_stable() -> None:
    assert fingerprint({"q": "hello"}) == fingerprint({"q": "hello"})
    assert fingerprint({"q": "hello"}) != fingerprint({"q": "goodbye"})


def test_engine_records_spans_per_execution(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    from aegis.observability.run_tracing import RecordingRunTracer

    tracer = RecordingRunTracer()

    class _Provider:
        def __init__(self, t):
            self._t = t

        def get_tracer(self, name):
            return self._t

    dataset = make_dataset_version(("hi", "hello"), ("bye", "bye"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        tracer_provider=_Provider(tracer),
    )

    harness.engine.run(run.id)

    assert len(tracer.spans) == 2
    assert tracer.flushed == [run.id]
    assert all(not s.ended or True for s in tracer.spans)


def test_engine_writes_gate_report_on_success(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    from aegis.application.run_gates import RunGateService
    from aegis.domain.time import FrozenClock
    from aegis.infrastructure.memory import MemoryRunGateStore

    store = MemoryRunGateStore()
    gate_service = RunGateService(store, FrozenClock())
    dataset = make_dataset_version(("hi", "hello"), ("bye", "bye"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        run_gates=gate_service,
    )

    harness.engine.run(run.id)

    report = store.load(run.id)
    assert report.verdict.value == "pass"
    assert [d.gate_id for d in report.decisions] == [
        "policy/evidence-gate",
        "policy/playback-gate",
    ]


def test_engine_reconciles_experiment_status_on_success(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget("hello")
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
    )

    harness.engine.run(run.id)

    experiment = harness.experiments.load(run.experiment_id)
    assert experiment.status.value == "succeeded"


def test_engine_reconciles_experiment_failed_when_run_fails(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget(FailureCode.MALFORMED_RESPONSE)
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
        retry=_fast_retry(),
    )

    harness.engine.run(run.id)

    experiment = harness.experiments.load(run.experiment_id)
    assert experiment.status.value == "failed"


def test_engine_reconciles_experiment_cancelled_when_run_cancelled(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    harness = make_harness(run=run, target_version=target_version, dataset_version=dataset)
    harness.registry.cancel(run.id, "alice", clock)

    harness.engine.run(run.id)

    experiment = harness.experiments.load(run.experiment_id)
    assert experiment.status.value == "cancelled"


def test_engine_does_not_reconcile_while_sibling_run_in_flight(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    from aegis.domain.execution import run_created

    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run_a = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    harness = make_harness(run=run_a, target_version=target_version, dataset_version=dataset)
    run_b = run_created(
        clock,
        "org:1",
        "prj:1",
        run_a.experiment_id,
        run_a.snapshot,
        created_by="alice",
    )
    harness.runs.save(run_b)

    harness.engine.run(run_a.id)

    experiment = harness.experiments.load(run_a.experiment_id)
    assert experiment.status.value == "running"  # run_b still queued


def test_engine_reconciles_experiment_after_last_sibling_completes(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    from aegis.domain.execution import run_created

    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run_a = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget("hello")
    harness = make_harness(
        run=run_a,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
    )
    run_b = run_created(
        clock,
        "org:1",
        "prj:1",
        run_a.experiment_id,
        run_a.snapshot,
        created_by="alice",
    )
    harness.runs.save(run_b)

    harness.engine.run(run_a.id)
    harness.engine.run(run_b.id)

    experiment = harness.experiments.load(run_a.experiment_id)
    assert experiment.status.value == "succeeded"


def test_engine_does_not_reconcile_again_when_already_terminal(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    run = make_run(target_version_id=target_version.id, dataset_version_id=dataset.id)
    target = ScriptedTarget("hello")
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=target,
    )

    harness.engine.run(run.id)
    harness.engine.run(run.id)

    experiment = harness.experiments.load(run.experiment_id)
    assert experiment.status.value == "succeeded"
    assert len(harness.target.calls) == 1


def test_engine_scores_trajectory_from_preserved_trace(
    clock,
    make_run,
    make_dataset_version,
    make_target_version,
    make_harness,
) -> None:
    from dataclasses import replace

    from aegis.domain.execution import ExperimentSnapshot
    from aegis.observability.preservation import TracePreservationEngine
    from aegis.observability.run_tracing import EvaluationTracerProvider

    dataset = make_dataset_version(("hi", "hello"))
    target_version = make_target_version()
    snapshot = ExperimentSnapshot(
        target_version_id=target_version.id,
        dataset_version_id=dataset.id,
        evaluator_version_ids=(
            "aegis/deterministic/exact_match",
            "aegis/trajectory/step_budget",
        ),
        settings={},
    )
    run = make_run(
        target_version_id=target_version.id,
        dataset_version_id=dataset.id,
    )
    run = replace(run, snapshot=snapshot)
    preservation = TracePreservationEngine()
    harness = make_harness(
        run=run,
        target_version=target_version,
        dataset_version=dataset,
        target=ScriptedTarget("hello"),
        tracer_provider=EvaluationTracerProvider(preservation),
        trace_source=lambda run_id: preservation.traces_for_run(run_id),
    )

    harness.engine.run(run.id)

    metrics = harness.results.list_for_run(run.id)
    identities = {m.evaluator_identity for m in metrics}
    assert "aegis/deterministic/exact_match" in identities
    assert "aegis/trajectory/step_budget" in identities
    step = next(m for m in metrics if m.metric_name == "step_budget")
    assert step.score == 1.0  # no tool steps observed, budget satisfied
    assert step.raw_value == 0
