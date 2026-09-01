"""Evidence record factory: assembles a complete, write-once EvidenceRecord.

A record is only produced when the score carries the provenance it claims: the
execution, experiment, target, and dataset must all be named, and the
provenance snapshot is content-addressed so the configuration cannot be silently
changed underneath a published score.
"""

from __future__ import annotations

from collections.abc import Iterable

from aegis.domain import (
    DatasetVersion,
    ExecutionRecord,
    Experiment,
    MetricResult,
    TargetVersion,
)
from aegis.domain.identifiers import new_id
from aegis.domain.time import Clock
from aegis.security.models import DataClassification

from .models import ArtifactReference, EvidenceRecord, ProvenanceSnapshot
from .ports import EvidenceRepository
from .provenance import build_provenance


def build_evidence_record(
    clock: Clock,
    result: MetricResult,
    execution: ExecutionRecord,
    experiment: Experiment,
    target_version: TargetVersion,
    dataset_version: DatasetVersion,
    provenance: ProvenanceSnapshot,
    artifact_references: Iterable[ArtifactReference] = (),
    created_by: str = "aegis",
    classification: DataClassification = DataClassification.INTERNAL,
) -> EvidenceRecord:
    """Create the write-once evidence record that backs one metric result."""
    if result.execution_id != execution.id:
        from aegis.domain import EvidenceViolation

        raise EvidenceViolation(
            f"metric {result.id!r} references execution {result.execution_id!r}, "
            f"not {execution.id!r}"
        )
    return EvidenceRecord(
        id=new_id("evd"),
        metric_result_id=result.id,
        run_id=result.run_id,
        execution_id=execution.id,
        experiment_id=experiment.id,
        evaluator_identity=result.evaluator_identity,
        evaluator_version=result.evaluator_version,
        dataset_version_id=dataset_version.id,
        target_version_id=target_version.id,
        artifact_references=tuple(artifact_references),
        provenance=provenance,
        classification=classification,
        created_at=clock.now(),
        created_by=created_by,
        judge_model=result.judge_model,
        judge_prompt_version=result.judge_prompt_version,
    )


def link_evidence_to_score(
    repository: EvidenceRepository,
    clock: Clock,
    result: MetricResult,
    execution: ExecutionRecord,
    experiment: Experiment,
    target_version: TargetVersion,
    dataset_version: DatasetVersion,
) -> EvidenceRecord:
    """Persist the evidence record and return it; a duplicate result id is refused."""
    provenance = build_provenance(
        clock,
        experiment,
        target_version,
        dataset_version,
        (result.evaluator_identity,),
        experiment.snapshot.policy_version_id,
    )
    record = build_evidence_record(
        clock,
        result,
        execution,
        experiment,
        target_version,
        dataset_version,
        provenance,
    )
    if repository.exists(record.id):
        from aegis.domain import Conflict

        raise Conflict(f"evidence record {record.id!r} already persisted")
    repository.persist(record)
    return record


__all__ = ["EvidenceRecord", "build_evidence_record", "link_evidence_to_score"]
