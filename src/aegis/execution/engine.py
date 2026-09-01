"""The execution engine: bounded, cancellable, evidence-preserving run loop.

Composes the target adapter (via TargetClient), the scoring gateway
(EvaluationGateway), bounded retries and mandatory timeouts, and leaves partial
evidence intact on every terminal path (failure-architecture.md).

At-least-once workers may redeliver a job; engine.run() is idempotent: a
terminal run is returned untouched.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import replace

from aegis.application.ports import (
    CancellationRegistry,
    DataCatalog,
    EvaluationGateway,
    ExecutionRepository,
    ResultRepository,
    RunRepository,
    TargetClient,
    TargetInvocation,
    TargetInvocationError,
    TargetInvocationRequest,
    summarize_evidence,
)
from aegis.domain import (
    EvidenceReference,
    FailureCode,
    FailureInfo,
    Run,
    RunStatus,
    TargetVersion,
    TestCase,
    classify_failure,
)
from aegis.domain.execution import (
    ExecutionOutcome,
    ExecutionRecord,
    TokenUsage,
    new_execution,
)
from aegis.domain.time import Clock
from aegis.execution.retry import RetryPolicy
from aegis.execution.timeout import TimeoutPolicy


def fingerprint(value: object) -> str:
    """Stable fingerprint for test-case IO, stored on evidence references."""
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def _as_outcome(invocation: TargetInvocation) -> ExecutionOutcome:
    """Convert an adapter invocation into the domain outcome shape."""
    return ExecutionOutcome(
        output=invocation.output,
        latency_ms=invocation.latency_ms,
        tokens=TokenUsage(
            input_tokens=invocation.input_tokens,
            output_tokens=invocation.output_tokens,
        ),
        cost_usd=invocation.cost_usd,
        trace_artifact_id=invocation.trace_artifact_id,
    )


class ExecutionEngine:
    def __init__(
        self,
        client: TargetClient,
        gateway: EvaluationGateway,
        runs: RunRepository,
        executions: ExecutionRepository,
        results: ResultRepository,
        catalog: DataCatalog,
        cancellations: CancellationRegistry,
        clock: Clock,
        retry: RetryPolicy,
        timeouts: TimeoutPolicy,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._gateway = gateway
        self._runs = runs
        self._executions = executions
        self._results = results
        self._catalog = catalog
        self._cancellations = cancellations
        self._clock = clock
        self._retry = retry
        self._timeouts = timeouts
        self._sleep = sleep

    def run(self, run_id: str) -> Run:
        run = self._runs.load(run_id)
        if run.status.terminal:
            return run

        now = self._clock.now()
        if run.status is RunStatus.RETRYING:
            run = run.resume()
        elif run.status is RunStatus.QUEUED:
            run = run.start(now)
        else:
            run = run  # RUNNING: redelivery resumes the run in place
        self._runs.save(run)

        started_at = run.started_at
        assert started_at is not None  # start()/resume() set started_at before this point
        dataset = self._catalog.load_dataset_version(run.snapshot.dataset_version_id)
        target = self._catalog.load_target_version(run.snapshot.target_version_id)
        overall_deadline = self._timeouts.deadline(
            started_at, self._timeouts.per_experiment_seconds
        )
        target_deadline = self._timeouts.deadline(started_at, self._timeouts.per_target_seconds)

        completed: list[ExecutionRecord] = []
        fatal: FailureInfo | None = None

        for sequence, test_case in enumerate(dataset.test_cases):
            if self._cancellations.is_cancelled(run.id):
                fatal = FailureInfo(
                    FailureCode.AGENT_LOOP, "cancelled by operator", self._clock.now()
                )
                break
            if self._clock.now() >= overall_deadline:
                fatal = FailureInfo(
                    FailureCode.EXPERIMENT_TIMEOUT,
                    "per-experiment deadline passed",
                    self._clock.now(),
                )
                break

            execution = new_execution(
                self._clock,
                run,
                sequence,
                test_case.id,
                target.id,
                dataset.id,
            )
            execution = execution.start(self._clock.now())
            self._executions.save(execution)

            result, used_retries = self._invoke_with_retry(
                execution,
                run,
                target,
                test_case,
                target_deadline,
                overall_deadline,
            )

            if isinstance(result, FailureInfo):
                execution = execution.fail(result, self._clock.now())
                self._executions.save(execution)
                completed.append(execution)
                fatal = result
                break

            outcome = _as_outcome(result)
            execution = replace(execution, retries=used_retries)
            trace_id = outcome.trace_artifact_id or f"trace/{execution.id}"
            outcome = replace(outcome, trace_artifact_id=trace_id)
            execution = execution.succeed(
                outcome,
                self._clock.now(),
                evidence=(
                    EvidenceReference(
                        execution_id=execution.id,
                        dataset_case_id=test_case.id,
                        trace_artifact_id=trace_id,
                        input_fingerprint=fingerprint(test_case.input),
                        expected_fingerprint=fingerprint(test_case.expected),
                    ),
                ),
            )
            self._executions.save(execution)
            completed.append(execution)

            metrics = self._gateway.evaluate(
                execution,
                test_case.id,
                target,
                run.snapshot.evaluator_version_ids,
                dict(run.snapshot.settings),
            )
            self._results.persist(metrics)

        summary = summarize_evidence(
            len(dataset.test_cases), completed, partial=len(completed) < len(dataset.test_cases)
        )

        if self._cancellations.is_cancelled(run.id):
            cancelled_by = self._cancellations.who_cancelled(run.id)
            if fatal is None or fatal.code is FailureCode.AGENT_LOOP:
                fatal = None
            run = run.cancel(cancelled_by or "system", self._clock.now(), summary)
        elif fatal is None:
            run = run.succeed(summary, self._clock.now())
        else:
            run = run.fail(fatal, summary, self._clock.now())
        run = replace(run, executions=tuple(ex.id for ex in completed))
        self._runs.save(run)
        return run

    def _invoke_with_retry(
        self,
        execution: ExecutionRecord,
        run: Run,
        target: TargetVersion,
        test_case: TestCase,
        target_deadline,
        overall_deadline,
    ) -> tuple[TargetInvocation | FailureInfo, int]:
        attempt = 0
        active = execution
        while True:
            if self._cancellations.is_cancelled(run.id):
                return (
                    FailureInfo(FailureCode.AGENT_LOOP, "cancelled by operator", self._clock.now()),
                    attempt,
                )
            if self._clock.now() >= overall_deadline:
                return (
                    FailureInfo(
                        FailureCode.EXPERIMENT_TIMEOUT,
                        "per-experiment deadline passed",
                        self._clock.now(),
                    ),
                    attempt,
                )
            if self._clock.now() >= target_deadline:
                return (
                    FailureInfo(
                        FailureCode.TARGET_TIMEOUT,
                        "per-target deadline passed",
                        self._clock.now(),
                    ),
                    attempt,
                )
            try:
                invocation = self._client.invoke(
                    TargetInvocationRequest(
                        test_case_id=test_case.id,
                        target_version_id=target.id,
                        payload=test_case.input,
                        metadata=dict(target.config),
                    ),
                    timeout_seconds=self._timeouts.per_test_seconds,
                )
                return invocation, attempt
            except TargetInvocationError as error:
                if not self._retry.should_retry(classify_failure(error.code), attempt):
                    return (
                        FailureInfo(error.code, error.message, self._clock.now()),
                        attempt,
                    )
                self._sleep(self._retry.delay_for(attempt))
                attempt += 1
                active = active.retried()
                self._executions.save(active)
            except Exception as error:  # noqa: BLE001 — adapter boundary is opaque to the engine
                return (
                    FailureInfo(
                        FailureCode.UNKNOWN,
                        f"unexpected target failure: {error}",
                        self._clock.now(),
                    ),
                    attempt,
                )


__all__ = ["ExecutionEngine", "fingerprint"]
