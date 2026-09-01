"""Executions and experiment runs: the async evaluation lifecycle.

Implements the execution state machine from failure-architecture.md. Runs and
executions are write-once records; every state transition returns a new
immutable value so history is never rewritten. Failed and cancelled states are
always distinguishable, and partial evidence is never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .events import DomainEvent
from .exceptions import InvalidState, ValidationFailed
from .experiments import ExperimentSnapshot
from .failures import FailureClass, FailureCode, classify_failure
from .identifiers import new_id
from .results import EvidenceReference
from .time import Clock


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        )


@dataclass(frozen=True)
class FailureInfo:
    code: FailureCode
    message: str
    occurred_at: datetime
    failure_class: FailureClass | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "failure_class",
            self.failure_class or classify_failure(self.code),
        )


@dataclass(frozen=True)
class EvidenceSummary:
    total_executions: int
    completed_executions: int
    evidence_reference_count: int
    partial_preserved: bool = False

    @property
    def completed(self) -> bool:
        return self.completed_executions >= self.total_executions


@dataclass(frozen=True)
class Run:
    """The user-facing unit of asynchronous execution (async-execution-contract.md)."""

    id: str
    organization_id: str
    project_id: str
    experiment_id: str
    snapshot: ExperimentSnapshot
    created_by: str
    created_at: datetime
    status: RunStatus = RunStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    evidence_summary: EvidenceSummary | None = None
    executions: tuple[str, ...] = ()
    error: FailureInfo | None = None
    cancelled_by: str | None = None
    cancelled_at: datetime | None = None
    idempotency_key: str | None = None

    def _require_active(self) -> None:
        if self.status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED):
            raise InvalidState(f"run {self.id!r} is already {self.status.value}")

    def start(self, now: datetime) -> Run:
        self._require_active()
        if self.status is not RunStatus.QUEUED:
            raise InvalidState(f"run {self.id!r} is {self.status.value}, not queued")
        return self._with(status=RunStatus.RUNNING, started_at=now)

    def mark_retrying(self) -> Run:
        if self.status is not RunStatus.RUNNING:
            raise InvalidState(f"run {self.id!r} is not running")
        return self._with(status=RunStatus.RETRYING)

    def resume(self) -> Run:
        if self.status is not RunStatus.RETRYING:
            raise InvalidState(f"run {self.id!r} is not retrying")
        return self._with(status=RunStatus.RUNNING)

    def record_partial(self, summary: EvidenceSummary, now: datetime) -> Run:
        self._require_active()
        return self._with(
            status=RunStatus.PARTIAL,
            evidence_summary=summary,
            started_at=self.started_at or now,
        )

    def succeed(self, summary: EvidenceSummary, now: datetime) -> Run:
        self._require_active()
        return self._with(
            status=RunStatus.SUCCEEDED,
            evidence_summary=summary,
            finished_at=now,
        )

    def fail(self, error: FailureInfo, summary: EvidenceSummary, now: datetime) -> Run:
        self._require_active()
        return self._with(
            status=RunStatus.FAILED,
            error=error,
            evidence_summary=summary,
            finished_at=now,
        )

    def cancel(
        self,
        identity: str,
        now: datetime,
        summary: EvidenceSummary | None = None,
    ) -> Run:
        self._require_active()
        return self._with(
            status=RunStatus.CANCELLED,
            cancelled_by=identity,
            cancelled_at=now,
            finished_at=now,
            evidence_summary=summary or self.evidence_summary,
        )

    def _with(self, **changes: Any) -> Run:
        from dataclasses import replace

        return replace(self, **changes)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ExecutionOutcome:
    output: str
    latency_ms: float
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    trace_artifact_id: str | None = None


@dataclass(frozen=True)
class ExecutionRecord:
    """A single target invocation against one test case (write-once)."""

    id: str
    run_id: str
    sequence: int
    test_case_id: str
    target_version_id: str
    dataset_version_id: str
    status: ExecutionStatus = ExecutionStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome: ExecutionOutcome | None = None
    evidence_references: tuple[EvidenceReference, ...] = ()
    failure: FailureInfo | None = None
    cancelled_by: str | None = None
    retries: int = 0

    def start(self, now: datetime) -> ExecutionRecord:
        if self.status is not ExecutionStatus.QUEUED:
            raise InvalidState(f"execution {self.id!r} is not queued")
        return self._with(status=ExecutionStatus.RUNNING, started_at=now)

    def retried(self) -> ExecutionRecord:
        if self.status is not ExecutionStatus.RUNNING:
            raise InvalidState(f"execution {self.id!r} is not running")
        return self._with(status=ExecutionStatus.QUEUED, retries=self.retries + 1)

    def succeed(
        self,
        outcome: ExecutionOutcome,
        now: datetime,
        evidence: tuple[EvidenceReference, ...] = (),
    ) -> ExecutionRecord:
        if self.status is not ExecutionStatus.RUNNING:
            raise InvalidState(f"execution {self.id!r} is not running")
        return self._with(
            status=ExecutionStatus.SUCCEEDED,
            outcome=outcome,
            evidence_references=self.evidence_references + evidence,
            finished_at=now,
        )

    def fail(self, failure: FailureInfo, now: datetime) -> ExecutionRecord:
        # Failed and cancelled must be distinguishable; partial evidence is retained.
        return self._with(
            status=ExecutionStatus.FAILED,
            failure=failure,
            finished_at=now,
        )

    def cancel(self, identity: str, now: datetime) -> ExecutionRecord:
        return self._with(
            status=ExecutionStatus.CANCELLED,
            cancelled_by=identity,
            finished_at=now,
        )

    def _with(self, **changes: Any) -> ExecutionRecord:
        from dataclasses import replace

        return replace(self, **changes)


def new_execution(
    clock: Clock,
    run: Run,
    sequence: int,
    test_case_id: str,
    target_version_id: str,
    dataset_version_id: str,
) -> ExecutionRecord:
    if run.status is not RunStatus.RUNNING:
        raise InvalidState(f"run {run.id!r} must be running before executions are created")
    if sequence < 0:
        raise ValidationFailed("execution sequence must be non-negative")
    return ExecutionRecord(
        id=new_id("exe"),
        run_id=run.id,
        sequence=sequence,
        test_case_id=test_case_id,
        target_version_id=target_version_id,
        dataset_version_id=dataset_version_id,
        created_at=clock.now(),
    )


def run_created(
    clock: Clock,
    organization_id: str,
    project_id: str,
    experiment_id: str,
    snapshot: ExperimentSnapshot,
    created_by: str,
    idempotency_key: str | None = None,
) -> Run:
    return Run(
        id=new_id("run"),
        organization_id=organization_id,
        project_id=project_id,
        experiment_id=experiment_id,
        snapshot=snapshot,
        created_by=created_by,
        created_at=clock.now(),
        idempotency_key=idempotency_key,
    )


def run_started(clock: Clock, run: Run) -> tuple[Run, DomainEvent]:
    started = run.start(clock.now())
    from .events import emit

    event = emit(
        clock,
        "run.started",
        "Run",
        started.id,
        experiment_id=started.experiment_id,
        status=started.status.value,
    )
    return started, event


def run_completed(clock: Clock, run: Run, summary: EvidenceSummary) -> tuple[Run, DomainEvent]:
    finished = run.succeed(summary, clock.now())
    from .events import emit

    event = emit(
        clock,
        "run.succeeded",
        "Run",
        finished.id,
        experiment_id=finished.experiment_id,
        completed_executions=summary.completed_executions,
    )
    return finished, event


__all__ = [
    "EvidenceSummary",
    "ExecutionOutcome",
    "ExecutionRecord",
    "ExecutionStatus",
    "FailureInfo",
    "Run",
    "RunStatus",
    "TokenUsage",
    "new_execution",
    "run_completed",
    "run_created",
    "run_started",
]
