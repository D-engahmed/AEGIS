"""Pydantic request/response models for the HTTP interface (layer 03).

These are the public wire contract. They are deliberately thin: they mirror
domain/application value objects without leaking dataclasses or enums into the
API consumers. All timestamps are ISO-8601.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExperimentSnapshotIn(ApiModel):
    """The immutable evaluation configuration pinned at creation time."""

    target_version_id: str
    dataset_version_id: str
    evaluator_version_ids: list[str] = Field(default_factory=list)
    policy_version_id: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ExperimentCreateIn(ApiModel):
    name: str
    project_id: str
    snapshot: ExperimentSnapshotIn


class ExperimentOut(ApiModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    status: str
    created_at: datetime
    clone_of: str | None = None


class RunOut(ApiModel):
    run_id: str
    experiment_id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    evidence_summary: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancelled_by: str | None = None
    cancelled_at: datetime | None = None


class RunSubmitIn(ApiModel):
    experiment_id: str
    idempotency_key: str | None = None


class MetricResultOut(ApiModel):
    id: str
    run_id: str
    execution_id: str
    metric_name: str
    score: float | None
    reason: str | None
    severity: str | None


class ArtifactRefOut(ApiModel):
    artifact_id: str
    artifact_type: str
    storage_key: str
    content_hash: str
    size_bytes: int
    content_type: str
    created_at: datetime


class ProvenanceOut(ApiModel):
    experiment_id: str
    target_version_id: str
    target_config_hash: str
    dataset_version_id: str
    dataset_hash: str
    evaluator_identities: list[str]
    evaluator_config_hash: str
    policy_version_id: str | None
    snapshot_timestamp: datetime


class EvidenceRecordOut(ApiModel):
    id: str
    metric_result_id: str
    run_id: str
    execution_id: str
    experiment_id: str
    evaluator_identity: str
    evaluator_version: str
    dataset_version_id: str
    target_version_id: str
    classification: str
    created_at: datetime
    created_by: str
    provenance: ProvenanceOut


class TrendPointOut(ApiModel):
    timestamp: datetime
    score: float
    run_id: str


class TrendReportOut(ApiModel):
    metric_name: str
    data_points: list[TrendPointOut]
    overall_trend: str
    analyzed_at: datetime


class HealthCheckOut(ApiModel):
    name: str
    status: str
    detail: str | None = None


class HealthSummaryOut(ApiModel):
    overall: str
    checks: list[HealthCheckOut]


class TokenOut(ApiModel):
    token: str
    expires_at: datetime
    authentication_method: str


class PiiRedactIn(ApiModel):
    text: str


class PiiRedactOut(ApiModel):
    redacted: str
    pii_spans: list[dict[str, Any]]


class GateDecisionOut(ApiModel):
    gate_id: str
    verdict: str
    reason: str
    severity: str


class RunVerdictOut(ApiModel):
    run_id: str
    verdict: str
    decisions: list[GateDecisionOut]
    evaluated_at: datetime
    overridden: bool
    override: dict[str, Any] | None = None


class GateOverrideIn(ApiModel):
    reason: str


__all__ = [
    "ApiModel",
    "ArtifactRefOut",
    "EvidenceRecordOut",
    "ExperimentCreateIn",
    "ExperimentOut",
    "ExperimentSnapshotIn",
    "GateDecisionOut",
    "GateOverrideIn",
    "HealthCheckOut",
    "HealthSummaryOut",
    "MetricResultOut",
    "PiiRedactIn",
    "PiiRedactOut",
    "ProvenanceOut",
    "RunOut",
    "RunSubmitIn",
    "RunVerdictOut",
    "TokenOut",
    "TrendPointOut",
    "TrendReportOut",
]
