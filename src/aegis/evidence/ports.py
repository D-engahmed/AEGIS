"""Evidence ports: write-once storage, provenance queries, and the graph.

Concrete implementations live in the infrastructure layer (PostgreSQL for the
records, S3-compatible object storage for artifacts); every consumer depends on
these protocols so the store can be swapped without touching policy or the
interface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    ArtifactReference,
    ArtifactType,
    EvidenceEdge,
    EvidenceGraphQuery,
    EvidenceGraphResult,
    EvidenceRecord,
    ProvenanceSnapshot,
)


@runtime_checkable
class EvidenceRepository(Protocol):
    """Write-once evidence record storage."""

    def persist(self, record: EvidenceRecord) -> None: ...
    def get(self, evidence_id: str) -> EvidenceRecord: ...
    def list_for_run(self, run_id: str) -> list[EvidenceRecord]: ...
    def list_for_metric_result(self, metric_result_id: str) -> list[EvidenceRecord]: ...
    def exists(self, evidence_id: str) -> bool: ...


@runtime_checkable
class EvidenceGraphStore(Protocol):
    """Build and query the evidence graph."""

    def add_edge(self, edge: EvidenceEdge) -> None: ...
    def remove_node(self, entity_type: str, entity_id: str) -> None: ...
    def query(self, query: EvidenceGraphQuery) -> EvidenceGraphResult: ...
    def edges_for(self, entity_type: str, entity_id: str) -> list[EvidenceEdge]: ...


@runtime_checkable
class ProvenanceQuery(Protocol):
    """Look up provenance for a score or execution."""

    def provenance_for_result(self, metric_result_id: str) -> ProvenanceSnapshot: ...
    def provenance_for_execution(self, execution_id: str) -> ProvenanceSnapshot: ...


@runtime_checkable
class ArtifactManager(Protocol):
    """Store and retrieve large payloads, keeping only references in records."""

    def store(
        self,
        artifact_type: ArtifactType,
        content: bytes,
        metadata: dict,
    ) -> ArtifactReference: ...
    def retrieve(self, artifact_id: str) -> bytes: ...
    def get_reference(self, artifact_id: str) -> ArtifactReference: ...
    def delete(self, artifact_id: str) -> None: ...


__all__ = [
    "ArtifactManager",
    "EvidenceGraphStore",
    "EvidenceRepository",
    "ProvenanceQuery",
]
