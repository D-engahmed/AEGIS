"""Evidence endpoints: immutable record listing, retrieval, and provenance."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..mappers import provenance_out, record_out
from ..schemas import EvidenceRecordOut, ProvenanceOut

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/runs/{run_id}", response_model=list[EvidenceRecordOut])
def list_run_evidence(
    run_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[EvidenceRecordOut]:
    """List write-once evidence records for a run."""
    actor.organization.require_membership(actor.context.user_id)
    container.run_service.require_run(actor.organization, run_id)
    records = container.evidence_repository.list_for_run(run_id)
    return [record_out(r) for r in records]


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
    container.run_service.require_run(actor.organization, records[0].run_id)
    snapshot = records[0].provenance
    return provenance_out(snapshot)


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
    container.run_service.require_run(actor.organization, record.run_id)
    return record_out(record)


__all__ = ["router"]
