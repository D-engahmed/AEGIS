"""Evidence graph: provenance links between experiments, executions, and scores.

In-memory adjacency-list graph with bounded BFS traversal. Persistence of the
same structure in PostgreSQL lives in the infrastructure layer behind the
EvidenceGraphStore protocol.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from aegis.domain import ImmutableResourceViolation

from .models import (
    EvidenceEdge,
    EvidenceGraphQuery,
    EvidenceGraphResult,
    EvidenceNode,
)
from .ports import EvidenceGraphStore


class InMemoryEvidenceGraph(EvidenceGraphStore):
    """Append-only graph: edges are added, never mutated or removed."""

    def __init__(self) -> None:
        self._edges: list[EvidenceEdge] = []
        self._indexed: dict[tuple[str, str], list[EvidenceEdge]] = {}
        self._metadata: dict[tuple[str, str], dict] = {}

    def add_edge(self, edge: EvidenceEdge) -> None:
        key = (edge.from_entity_type, edge.from_entity_id)
        self._edges.append(edge)
        self._indexed.setdefault(key, []).append(edge)

    def remove_node(self, entity_type: str, entity_id: str) -> None:
        del entity_type, entity_id
        raise ImmutableResourceViolation("evidence graph is append-only; nodes are never removed")

    def query(self, query: EvidenceGraphQuery) -> EvidenceGraphResult:
        nodes: dict[tuple[str, str], EvidenceNode] = {}
        edges: list[EvidenceEdge] = []
        frontier = deque([(query.root_entity_type, query.root_entity_id, 0)])
        while frontier:
            entity_type, entity_id, depth = frontier.popleft()
            key = (entity_type, entity_id)
            node = EvidenceNode(
                entity_type=entity_type,
                entity_id=entity_id,
                metadata=self._metadata.get(key, {}),
            )
            nodes[key] = node
            if depth >= query.depth:
                continue
            for edge in self._edges_for(entity_type, entity_id):
                if query.edge_types is not None and edge.edge_type not in query.edge_types:
                    continue
                edges.append(edge)
                target = (edge.to_entity_type, edge.to_entity_id)
                if target not in nodes:
                    frontier.append((target[0], target[1], depth + 1))
        return EvidenceGraphResult(
            root=EvidenceNode(
                entity_type=query.root_entity_type,
                entity_id=query.root_entity_id,
                metadata=self._metadata.get((query.root_entity_type, query.root_entity_id), {}),
            ),
            nodes=tuple(nodes.values()),
            edges=tuple(dict.fromkeys(edges)),
        )

    def edges_for(self, entity_type: str, entity_id: str) -> list[EvidenceEdge]:
        return list(self._indexed.get((entity_type, entity_id), []))

    def _edges_for(self, entity_type: str, entity_id: str) -> Iterable[EvidenceEdge]:
        return iter(self._indexed.get((entity_type, entity_id), []))


__all__ = ["InMemoryEvidenceGraph"]
