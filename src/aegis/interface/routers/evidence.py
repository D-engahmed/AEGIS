"""Evidence endpoints: immutable record listing, retrieval, and provenance."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from aegis.evidence.models import EvidenceRecord
from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..schemas import EvidenceRecordOut, ProvenanceOut

router = APIRouter(prefix="/evidence", tags=["evidence"])


def _record_out(record: EvidenceRecord) -> EvidenceRecordOut:
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
        provenance=ProvenanceOut(
            experiment_id=record.provenance.experiment_id,
            target_version_id=record.provenance.target_version_id,
            target_config_hash=record.provenance.target_config_hash,
            dataset_version_id=record.provenance.dataset_version_id,
            dataset_hash=record.provenance.dataset_hash,
            evaluator_identities=list(record.provenance.evaluator_identities),
            evaluator_config_hash=record.provenance.evaluator_config_hash,
            policy_version_id=record.provenance.policy_version_id,
            snapshot_timestamp=record.provenance.snapshot_timestamp,
        ),
    )


@router.get("/runs/{run_id}", response_model=list[EvidenceRecordOut])
def list_run_evidence(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[EvidenceRecordOut]:
    """List write-once evidence records for a run."""
    actor.organization.require_membership(actor.context.user_id)
    records = container.evidence_repository.list_for_run(run_id)
    return [_record_out(r) for r in records]


@router.get("/provenance/{metric_result_id}", response_model=ProvenanceOut)
def get_provenance(
    metric_result_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> ProvenanceOut:
    """Fetch the provenance snapshot behind a metric result."""
    actor.organization.require_membership(actor.context.user_id)
    records = container.evidence_repository.list_for_metric_result(metric_result_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no evidence found for metric result {metric_result_id!r}",
        )
    snapshot = records[0].provenance
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


@router.get("/{evidence_id}", response_model=EvidenceRecordOut)
def get_evidence(
    evidence_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> EvidenceRecordOut:
    """Fetch a single evidence record by id."""
    actor.organization.require_membership(actor.context.user_id)
    try:
        record = container.evidence_repository.get(evidence_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _record_out(record)


__all__ = ["router"]
