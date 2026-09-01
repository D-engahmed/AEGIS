"""Evidence records and graph: the immutable provenance backbone.

Carries the "no score without evidence" rule into a queryable, immutable record
set: every score links back through provenance to the exact target version,
dataset version, evaluator, and configuration that produced it
(evidence-architecture.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from aegis.security.models import DataClassification


class ArtifactType(StrEnum):
    TRACE = "trace"
    LOG = "log"
    REPORT = "report"
    INPUT = "input"
    EXPECTED = "expected"
    RAW_OUTPUT = "raw_output"


class EdgeType(StrEnum):
    GENERATED_BY = "generated_by"
    CONTAINS = "contains"
    EVALUATED_WITH = "evaluated_with"
    PRODUCED_BY = "produced_by"
    LINKED_TO = "linked_to"


@dataclass(frozen=True)
class ArtifactReference:
    """Pointer to a large payload held in object storage."""

    artifact_id: str
    artifact_type: ArtifactType
    storage_key: str
    content_hash: str
    size_bytes: int
    content_type: str
    created_at: datetime


@dataclass(frozen=True)
class ProvenanceSnapshot:
    """Immutable snapshot of every versioned input behind a score."""

    experiment_id: str
    target_version_id: str
    target_config_hash: str
    dataset_version_id: str
    dataset_hash: str
    evaluator_identities: tuple[str, ...]
    evaluator_config_hash: str
    policy_version_id: str | None
    snapshot_timestamp: datetime


@dataclass(frozen=True)
class EvidenceRecord:
    """Write-once metadata record for one score; never mutated."""

    id: str
    metric_result_id: str
    run_id: str
    execution_id: str
    experiment_id: str
    evaluator_identity: str
    evaluator_version: str
    dataset_version_id: str
    target_version_id: str
    artifact_references: tuple[ArtifactReference, ...]
    provenance: ProvenanceSnapshot
    classification: DataClassification
    created_at: datetime
    created_by: str
    judge_model: str | None = None
    judge_prompt_version: str | None = None


@dataclass(frozen=True)
class EvidenceEdge:
    from_entity_type: str
    from_entity_id: str
    to_entity_type: str
    to_entity_id: str
    edge_type: EdgeType


@dataclass(frozen=True)
class EvidenceNode:
    entity_type: str
    entity_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceGraphQuery:
    root_entity_type: str
    root_entity_id: str
    depth: int = 2
    edge_types: tuple[EdgeType, ...] | None = None


@dataclass(frozen=True)
class EvidenceGraphResult:
    root: EvidenceNode
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]


__all__ = [
    "ArtifactReference",
    "ArtifactType",
    "EdgeType",
    "EvidenceEdge",
    "EvidenceGraphQuery",
    "EvidenceGraphResult",
    "EvidenceNode",
    "EvidenceRecord",
    "ProvenanceSnapshot",
]
