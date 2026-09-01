"""Data-transfer objects consumed by the interface layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aegis.domain import EvidenceSummary, FailureInfo, Run


@dataclass(frozen=True)
class RunView:
    """The public representation of a run (async-execution-contract.md)."""

    run_id: str
    experiment_id: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    evidence_summary: EvidenceSummary | None
    error: FailureInfo | None
    cancelled_by: str | None
    cancelled_at: datetime | None

    @classmethod
    def from_run(cls, run: Run) -> RunView:
        return cls(
            run_id=run.id,
            experiment_id=run.experiment_id,
            status=run.status.value,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            evidence_summary=run.evidence_summary,
            error=run.error,
            cancelled_by=run.cancelled_by,
            cancelled_at=run.cancelled_at,
        )


__all__ = ["RunView"]
