"""In-memory adapters for every application port (tests, dev, REPL use).

All repositories reject concurrency-free axioms of the real stores: results
are write-once, runs load by idempotency key, and cancellation tokens are kept
per run. Nothing here may perform actual I/O.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from aegis.application.ports import CancellationRegistry
from aegis.domain import (
    Conflict,
    DatasetVersion,
    ExecutionRecord,
    Experiment,
    MetricResult,
    NotFound,
    Run,
    TargetVersion,
)
from aegis.domain.identifiers import new_id
from aegis.domain.time import Clock
from aegis.evidence.models import (
    ArtifactReference,
    ArtifactType,
    EvidenceRecord,
    ProvenanceSnapshot,
)
from aegis.execution.cancellation import CancellationToken
from aegis.policy.models import RunGateReport


class MemoryExperimentRepository:
    def __init__(self) -> None:
        self._items: dict[str, Experiment] = {}

    def save(self, experiment: Experiment) -> None:
        self._items[experiment.id] = experiment

    def load(self, experiment_id: str) -> Experiment:
        try:
            return self._items[experiment_id]
        except KeyError:
            raise NotFound(f"experiment {experiment_id!r} not found") from None

    def exists(self, experiment_id: str) -> bool:
        return experiment_id in self._items


class MemoryRunRepository:
    def __init__(self) -> None:
        self._items: dict[str, Run] = {}
        self._by_key: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._items[run.id] = run
        if run.idempotency_key is not None:
            self._by_key[run.idempotency_key] = run

    def load(self, run_id: str) -> Run:
        try:
            return self._items[run_id]
        except KeyError:
            raise NotFound(f"run {run_id!r} not found") from None

    def find_by_idempotency(self, key: str) -> Run | None:
        return self._by_key.get(key)


class MemoryExecutionRepository:
    """One live row per execution id (state transitions upsert), indexed by run."""

    def __init__(self) -> None:
        self._items: dict[str, ExecutionRecord] = {}

    def save(self, execution: ExecutionRecord) -> None:
        self._items[execution.id] = execution

    def load(self, execution_id: str) -> ExecutionRecord:
        try:
            return self._items[execution_id]
        except KeyError:
            raise NotFound(f"execution {execution_id!r} not found") from None

    def list_for_run(self, run_id: str) -> list[ExecutionRecord]:
        return [ex for ex in self._items.values() if ex.run_id == run_id]


class MemoryResultRepository:
    """Results are write-once: a duplicate metric id is a conflict."""

    def __init__(self) -> None:
        self._items: dict[str, MetricResult] = {}
        self._by_run: dict[str, list[MetricResult]] = {}

    def persist(self, results: Iterable[MetricResult]) -> None:
        for result in results:
            if result.id in self._items:
                raise Conflict(f"metric result {result.id!r} already persisted")
            self._items[result.id] = result
            self._by_run.setdefault(result.run_id, []).append(result)

    def list_for_run(self, run_id: str) -> list[MetricResult]:
        return list(self._by_run.get(run_id, []))


class InMemoryDataCatalog:
    def __init__(self) -> None:
        self._targets: dict[str, TargetVersion] = {}
        self._datasets: dict[str, DatasetVersion] = {}

    def register_target(self, version: TargetVersion) -> None:
        self._targets[version.id] = version

    def register_dataset(self, version: DatasetVersion) -> None:
        self._datasets[version.id] = version

    def load_target_version(self, target_version_id: str) -> TargetVersion:
        try:
            return self._targets[target_version_id]
        except KeyError:
            raise NotFound(f"target version {target_version_id!r} not found") from None

    def load_dataset_version(self, dataset_version_id: str) -> DatasetVersion:
        try:
            return self._datasets[dataset_version_id]
        except KeyError:
            raise NotFound(f"dataset version {dataset_version_id!r} not found") from None


class InMemoryCancellationRegistry(CancellationRegistry):
    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}

    def cancel(self, run_id: str, identity: str, clock: Clock) -> None:
        self._tokens[run_id] = CancellationToken(run_id, identity, clock.now())

    def is_cancelled(self, run_id: str) -> bool:
        return run_id in self._tokens

    def who_cancelled(self, run_id: str) -> str | None:
        token = self._tokens.get(run_id)
        return token.identity if token else None

    def clear(self) -> None:
        self._tokens.clear()


class MemoryQueue:
    """FIFO job queue with claim/complete/abandon semantics."""

    def __init__(self, job_ids: Iterable[str] = ()) -> None:
        self._pending: list[str] = list(job_ids)
        self._claimed: dict[str, int] = {}

    def put(self, job_id: str) -> None:
        self._pending.append(job_id)

    def claim(self) -> str | None:
        if not self._pending:
            return None
        job_id = self._pending.pop(0)
        self._claimed[job_id] = self._claimed.get(job_id, 0) + 1
        return job_id

    def complete(self, job_id: str) -> None:
        self._claimed.pop(job_id, None)

    def abandon(self, job_id: str) -> None:
        if job_id in self._claimed:
            del self._claimed[job_id]
            self._pending.insert(0, job_id)

    def pending(self) -> int:
        return len(self._pending)

    @property
    def claimed_ids(self) -> set[str]:
        return set(self._claimed)


class MemoryEvidenceRepository:
    """Write-once evidence records: duplicate persist is a conflict, no updates."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceRecord] = {}
        self._by_run: dict[str, list[EvidenceRecord]] = {}
        self._by_metric: dict[str, list[EvidenceRecord]] = {}

    def persist(self, record: EvidenceRecord) -> None:
        if record.id in self._items:
            raise Conflict(f"evidence record {record.id!r} already persisted")
        self._items[record.id] = record
        self._by_run.setdefault(record.run_id, []).append(record)
        self._by_metric.setdefault(record.metric_result_id, []).append(record)

    def get(self, evidence_id: str) -> EvidenceRecord:
        try:
            return self._items[evidence_id]
        except KeyError:
            raise NotFound(f"evidence record {evidence_id!r} not found") from None

    def list_for_run(self, run_id: str) -> list[EvidenceRecord]:
        return list(self._by_run.get(run_id, []))

    def list_for_metric_result(self, metric_result_id: str) -> list[EvidenceRecord]:
        return list(self._by_metric.get(metric_result_id, []))

    def exists(self, evidence_id: str) -> bool:
        return evidence_id in self._items


class MemoryProvenanceIndex:
    """Executes provenance_for_result / provenance_for_execution lookups."""

    def __init__(self) -> None:
        self._by_execution: dict[str, ProvenanceSnapshot] = {}
        self._by_metric: dict[str, ProvenanceSnapshot] = {}

    def index(self, record: EvidenceRecord) -> None:
        self._by_execution[record.execution_id] = record.provenance
        self._by_metric[record.metric_result_id] = record.provenance

    def provenance_for_result(self, metric_result_id: str) -> ProvenanceSnapshot:
        if metric_result_id not in self._by_metric:
            raise NotFound(f"no provenance indexed for metric result {metric_result_id!r}")
        return self._by_metric[metric_result_id]

    def provenance_for_execution(self, execution_id: str) -> ProvenanceSnapshot:
        if execution_id not in self._by_execution:
            raise NotFound(f"no provenance indexed for execution {execution_id!r}")
        return self._by_execution[execution_id]


class MemoryRunGateStore:
    """In-memory store for persisted run gate reports (override replaces)."""

    def __init__(self) -> None:
        self._reports: dict[str, RunGateReport] = {}

    def save(self, report: RunGateReport) -> None:
        self._reports[report.run_id] = report

    def load(self, run_id: str) -> RunGateReport:
        if run_id not in self._reports:
            raise NotFound(f"gate report for run {run_id!r} not found")
        return self._reports[run_id]

    def exists(self, run_id: str) -> bool:
        return run_id in self._reports


class MemoryArtifactManager:
    """In-memory object storage: content-hashes payloads, keeps references."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self._references: dict[str, ArtifactReference] = {}

    def store(
        self,
        artifact_type: ArtifactType,
        content: bytes,
        metadata: dict,
    ) -> ArtifactReference:
        digest = hashlib.sha256(content).hexdigest()
        reference = ArtifactReference(
            artifact_id=new_id("art"),
            artifact_type=artifact_type,
            storage_key=f"{artifact_type.value}/{digest}",
            content_hash=digest,
            size_bytes=len(content),
            content_type=metadata.get("content_type", "application/octet-stream"),
            created_at=metadata.get("created_at") or datetime.now(UTC),
        )
        self._blobs[reference.artifact_id] = content
        self._references[reference.artifact_id] = reference
        return reference

    def retrieve(self, artifact_id: str) -> bytes:
        if artifact_id not in self._blobs:
            raise NotFound(f"artifact {artifact_id!r} not found")
        return self._blobs[artifact_id]

    def get_reference(self, artifact_id: str) -> ArtifactReference:
        if artifact_id not in self._references:
            raise NotFound(f"artifact {artifact_id!r} not found")
        return self._references[artifact_id]

    def delete(self, artifact_id: str) -> None:
        self._blobs.pop(artifact_id, None)
        self._references.pop(artifact_id, None)


__all__ = [
    "InMemoryCancellationRegistry",
    "InMemoryDataCatalog",
    "MemoryArtifactManager",
    "MemoryEvidenceRepository",
    "MemoryExecutionRepository",
    "MemoryExperimentRepository",
    "MemoryProvenanceIndex",
    "MemoryQueue",
    "MemoryResultRepository",
    "MemoryRunGateStore",
    "MemoryRunRepository",
]
