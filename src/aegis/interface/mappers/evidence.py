"""Evidence mappers: records and provenance snapshots to wire schemas."""

from __future__ import annotations

from aegis.evidence.models import EvidenceRecord

from ..schemas import EvidenceRecordOut, ProvenanceOut


def provenance_out(snapshot) -> ProvenanceOut:
    return ProvenanceOut(
        experiment_id=snapshot.experiment_id,
        target_version_id=snapshot.target_version_id,
        target_config_hash=snapshot.target_config_hash,
        dataset_version_id=snapshot.dataset_version_id,
        dataset_hash=snapshot.dataset_hash,
        evaluator_identities=list(snapshot.evaluator_identities),
        evaluator_config_hash=snapshot.evaluator_config_hash,
        policy_version_id=snapshot.policy_version_id,
        snapshot_timestamp=snapshot.snapshot_timestamp,
    )


def record_out(record: EvidenceRecord) -> EvidenceRecordOut:
    return EvidenceRecordOut(
        id=record.id,
        metric_result_id=record.metric_result_id,
        run_id=record.run_id,
        execution_id=record.execution_id,
        experiment_id=record.experiment_id,
        evaluator_identity=record.evaluator_identity,
        evaluator_version=record.evaluator_version,
        dataset_version_id=record.dataset_version_id,
        target_version_id=record.target_version_id,
        classification=record.classification.value,
        created_at=record.created_at,
        created_by=record.created_by,
        provenance=provenance_out(record.provenance),
    )


__all__ = ["provenance_out", "record_out"]
