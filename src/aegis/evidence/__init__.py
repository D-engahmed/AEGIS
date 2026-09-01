"""Evidence layer (layer 09): immutable provenance records and the graph.

A score is never persisted without its evidence record; every record is
write-once and content-addressed back to the configuration that produced it.
The layer depends only on domain (01) and security (11) for classification;
storage adapters implement the ports in the infrastructure layer.
"""

from .build import build_evidence_record, link_evidence_to_score
from .graph import InMemoryEvidenceGraph
from .models import (
    ArtifactReference,
    ArtifactType,
    EdgeType,
    EvidenceEdge,
    EvidenceGraphQuery,
    EvidenceGraphResult,
    EvidenceNode,
    EvidenceRecord,
    ProvenanceSnapshot,
)
from .ports import (
    ArtifactManager,
    EvidenceGraphStore,
    EvidenceRepository,
    ProvenanceQuery,
)
from .provenance import build_provenance, content_hash

__all__ = [
    "ArtifactManager",
    "ArtifactReference",
    "ArtifactType",
    "EdgeType",
    "EvidenceEdge",
    "EvidenceGraphQuery",
    "EvidenceGraphResult",
    "EvidenceGraphStore",
    "EvidenceNode",
    "EvidenceRecord",
    "EvidenceRepository",
    "InMemoryEvidenceGraph",
    "ProvenanceQuery",
    "ProvenanceSnapshot",
    "build_evidence_record",
    "build_provenance",
    "content_hash",
    "link_evidence_to_score",
]
