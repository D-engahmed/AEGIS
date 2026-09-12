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


class TestCaseIn(ApiModel):
    input: Any
    expected: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TargetRegisterIn(ApiModel):
    """Register a target application and its first configuration version."""

    project_id: str
    name: str
    target_type: str = "llm_application"
    label: str = "1.0.0"
    config: dict[str, Any] = Field(default_factory=dict)
    commit_sha: str | None = None


class DatasetRegisterIn(ApiModel):
    """Register a dataset and a draft version with its initial test cases."""

    project_id: str
    name: str
    label: str = "1.0.0"
    test_cases: list[TestCaseIn] = Field(default_factory=list)


class CatalogTargetOut(ApiModel):
    id: str
    target_id: str
    project_id: str
    name: str
    target_type: str
    label: str
    config: dict[str, Any]
    created_at: datetime
    referenced: bool


class CatalogDatasetOut(ApiModel):
    id: str
    dataset_id: str
    project_id: str
    name: str
    label: str
    status: str
    test_case_count: int
    created_at: datetime


class CatalogOut(ApiModel):
    targets: list[CatalogTargetOut]
    datasets: list[CatalogDatasetOut]


class EvaluatorSpecOut(ApiModel):
    """A discoverable scoring plugin (deterministic or trajectory)."""

    identity: str
    version: str
    display_name: str
    metrics: list[str]
    requires_trace: bool = False
    severity: str = "info"
    unit: str | None = None


class ExperimentSnapshotOut(ApiModel):
    """The immutable configuration pinned at experiment creation time."""

    target_version_id: str
    dataset_version_id: str
    evaluator_version_ids: list[str] = Field(default_factory=list)
    policy_version_id: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ExperimentOut(ApiModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    status: str
    created_at: datetime
    clone_of: str | None = None
    snapshot: ExperimentSnapshotOut | None = None


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
    "CatalogDatasetOut",
    "CatalogOut",
    "CatalogTargetOut",
    "DatasetRegisterIn",
    "EvidenceRecordOut",
    "EvaluatorSpecOut",
    "ExperimentCreateIn",
    "ExperimentOut",
    "ExperimentSnapshotIn",
    "ExperimentSnapshotOut",
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
    "TargetRegisterIn",
    "TestCaseIn",
    "TokenOut",
    "TrendPointOut",
    "TrendReportOut",
]
