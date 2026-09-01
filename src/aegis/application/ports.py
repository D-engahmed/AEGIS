"""Ports: interfaces between application services and adapters.

Application services depend only on these protocols, never on concrete
repositories, queue clients, or target clients. Adaptors live in the
infrastructure and execution layers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aegis.domain import (
    DatasetVersion,
    EvidenceSummary,
    ExecutionRecord,
    Experiment,
    FailureCode,
    MetricResult,
    Run,
    TargetVersion,
)
from aegis.domain.time import Clock


@dataclass(frozen=True)
class TargetInvocationRequest:
    test_case_id: str
    target_version_id: str
    payload: object
    metadata: dict


@dataclass(frozen=True)
class TargetInvocation:
    output: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    trace_artifact_id: str | None = None


class TargetInvocationError(Exception):
    """A target invocation failed; the code maps to the failure taxonomy."""

    def __init__(self, code: FailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@runtime_checkable
class TargetClient(Protocol):
    """Adapter contract for invoking an external AI target (REST target adapter)."""

    def invoke(self, request: TargetInvocationRequest, timeout_seconds: float) -> TargetInvocation:
        """Invoke the target; raise TargetInvocationError on failure."""
        ...


@runtime_checkable
class EvaluationGateway(Protocol):
    """Scoring boundary: execution layer requests scores, evaluation computes."""

    def evaluate(
        self,
        execution: ExecutionRecord,
        test_case_id: str,
        target_version: TargetVersion,
        evaluator_version_ids: Iterable[str],
        settings: dict,
    ) -> list[MetricResult]: ...


@runtime_checkable
class ExperimentRepository(Protocol):
    def save(self, experiment: Experiment) -> None: ...

    def load(self, experiment_id: str) -> Experiment: ...

    def exists(self, experiment_id: str) -> bool: ...


@runtime_checkable
class RunRepository(Protocol):
    def save(self, run: Run) -> None: ...

    def load(self, run_id: str) -> Run: ...

    def find_by_idempotency(self, key: str) -> Run | None: ...


@runtime_checkable
class ExecutionRepository(Protocol):
    def save(self, execution: ExecutionRecord) -> None: ...

    def load(self, execution_id: str) -> ExecutionRecord: ...

    def list_for_run(self, run_id: str) -> list[ExecutionRecord]: ...


@runtime_checkable
class ResultRepository(Protocol):
    """Results are write-once; persisting an existing result id fails."""

    def persist(self, results: Iterable[MetricResult]) -> None: ...

    def list_for_run(self, run_id: str) -> list[MetricResult]: ...


@runtime_checkable
class DataCatalog(Protocol):
    def load_target_version(self, target_version_id: str) -> TargetVersion: ...

    def load_dataset_version(self, dataset_version_id: str) -> DatasetVersion: ...


@runtime_checkable
class Queue(Protocol):
    """At-least-once job queue abstraction (backed by Redis in production)."""

    def put(self, job_id: str) -> None: ...

    def claim(self) -> str | None: ...

    def complete(self, job_id: str) -> None: ...

    def abandon(self, job_id: str) -> None: ...

    def pending(self) -> int: ...


@runtime_checkable
class CancellationRegistry(Protocol):
    """Holds cooperative cancellation tokens per run."""

    def cancel(self, run_id: str, identity: str, clock: Clock) -> None: ...

    def is_cancelled(self, run_id: str) -> bool: ...

    def who_cancelled(self, run_id: str) -> str | None:
        """Identity of the canceller, used to stamp run.cancelled_by."""
        ...


def summarize_evidence(
    run_total: int,
    executions: Iterable[ExecutionRecord],
    partial: bool = False,
) -> EvidenceSummary:
    """Build the standard evidence summary from completed executions."""
    completed = list(executions)
    refs = sum(len(ex.evidence_references) for ex in completed)
    return EvidenceSummary(
        total_executions=run_total,
        completed_executions=len(completed),
        evidence_reference_count=refs,
        partial_preserved=partial,
    )


__all__ = [
    "CancellationRegistry",
    "DataCatalog",
    "EvaluationGateway",
    "ExecutionRepository",
    "ExperimentRepository",
    "Queue",
    "ResultRepository",
    "RunRepository",
    "TargetClient",
    "TargetInvocation",
    "TargetInvocationError",
    "TargetInvocationRequest",
    "summarize_evidence",
]
