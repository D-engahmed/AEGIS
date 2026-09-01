"""Metric results with full provenance and the "no score without evidence" rule.

A MetricResult cannot exist without evidence references that reach back to the
execution that produced it. Results are write-once: frozen, immutable, and
carrying evaluator identity, evaluator version, judge metadata, and confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .exceptions import AegisDomainError
from .identifiers import new_id
from .time import Clock


class EvidenceViolation(AegisDomainError):
    """A score was attempted without the evidence its provenance requires."""


@dataclass(frozen=True)
class EvidenceReference:
    """A stable link from a score to the evidence that produced it."""

    execution_id: str
    dataset_case_id: str
    trace_artifact_id: str | None = None
    input_fingerprint: str | None = None
    expected_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise EvidenceViolation("evidence reference requires an execution id")
        if not self.dataset_case_id:
            raise EvidenceViolation("evidence reference requires a dataset case id")
        if (
            self.trace_artifact_id is None
            and self.input_fingerprint is None
            and self.expected_fingerprint is None
        ):
            raise EvidenceViolation(
                "evidence reference requires at least a trace, input or expected artifact"
            )


@dataclass(frozen=True)
class MetricResult:
    """A write-once, evidence-backed score (evidence-architecture.md)."""

    id: str
    run_id: str
    execution_id: str
    test_case_id: str
    metric_name: str
    score: float
    evaluator_identity: str
    evaluator_version: str
    created_at: datetime
    evidence: tuple[EvidenceReference, ...]
    confidence: float = 1.0
    severity: str = "info"
    raw_value: float | None = None
    unit: str | None = None
    reason: str | None = None
    judge_model: str | None = None
    judge_prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise EvidenceViolation(f"score must be within [0, 1], got {self.score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise EvidenceViolation(f"confidence must be within [0, 1], got {self.confidence}")
        if not self.evidence:
            raise EvidenceViolation(f"metric {self.metric_name!r} has no evidence references")
        if not any(ref.execution_id == self.execution_id for ref in self.evidence):
            raise EvidenceViolation(
                f"metric {self.metric_name!r} evidence must reference "
                f"execution {self.execution_id!r}"
            )
        if not self.evaluator_identity or not self.evaluator_version:
            raise EvidenceViolation("metric results require evaluator identity and version")


def new_metric_result(
    clock: Clock,
    run_id: str,
    execution_id: str,
    test_case_id: str,
    metric_name: str,
    score: float,
    evaluator_identity: str,
    evaluator_version: str,
    evidence: tuple[EvidenceReference, ...],
    **meta: Any,
) -> MetricResult:
    """Build an evidence-checked, write-once metric result."""
    return MetricResult(
        id=new_id("mtr"),
        run_id=run_id,
        execution_id=execution_id,
        test_case_id=test_case_id,
        metric_name=metric_name,
        score=score,
        evaluator_identity=evaluator_identity,
        evaluator_version=evaluator_version,
        created_at=clock.now(),
        evidence=evidence,
        **meta,
    )


__all__ = [
    "EvidenceReference",
    "EvidenceViolation",
    "MetricResult",
    "new_metric_result",
]
