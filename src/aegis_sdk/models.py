"""Typed wire models for the AEGIS SDK.

These dataclasses mirror the JSON contract served by the AEGIS API
(``docs/api/``). Parsing is tolerant: unknown future fields are ignored and
optional fields default safely, so an older SDK keeps working against a newer
API in the same major version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value.endswith("Z"):
        return datetime.fromisoformat(value[:-1] + "+00:00")
    return datetime.fromisoformat(value)


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


@dataclass(frozen=True)
class ApiModel:
    """Base: tolerate unknown JSON fields and missing optional keys.

    Present keys are copied to fields of the same name; anything extra is
    ignored. Subclasses override ``parse`` only to coerce types (timestamps,
    nested models, lists).
    """

    @classmethod
    def parse(cls, data: dict[str, Any]) -> ApiModel:
        from dataclasses import fields

        return cls(**{fld.name: data[fld.name] for fld in fields(cls) if fld.name in data})


def _parse_list(model_type, items: list[Any] | None) -> list[Any]:
    return [model_type.parse(item) for item in (items or [])]


@dataclass(frozen=True)
class CatalogTarget(ApiModel):
    id: str = ""
    target_id: str = ""
    project_id: str = ""
    name: str = ""
    target_type: str = ""
    label: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    referenced: bool = False

    @classmethod
    def parse(cls, data: dict[str, Any]) -> CatalogTarget:
        return cls(
            id=data.get("id", ""),
            target_id=data.get("target_id", ""),
            project_id=data.get("project_id", ""),
            name=data.get("name", ""),
            target_type=data.get("target_type", ""),
            label=data.get("label", ""),
            config=data.get("config", {}) or {},
            created_at=_dt(data.get("created_at")),
            referenced=_bool(data.get("referenced")),
        )


@dataclass(frozen=True)
class CatalogDataset(ApiModel):
    id: str = ""
    dataset_id: str = ""
    project_id: str = ""
    name: str = ""
    label: str = ""
    status: str = ""
    test_case_count: int = 0
    created_at: datetime | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> CatalogDataset:
        return cls(
            id=data.get("id", ""),
            dataset_id=data.get("dataset_id", ""),
            project_id=data.get("project_id", ""),
            name=data.get("name", ""),
            label=data.get("label", ""),
            status=data.get("status", ""),
            test_case_count=_int(data.get("test_case_count")),
            created_at=_dt(data.get("created_at")),
        )


@dataclass(frozen=True)
class CatalogSummary(ApiModel):
    targets: list[CatalogTarget] = field(default_factory=list)
    datasets: list[CatalogDataset] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> CatalogSummary:
        return cls(
            targets=_parse_list(CatalogTarget, data.get("targets")),
            datasets=_parse_list(CatalogDataset, data.get("datasets")),
        )


@dataclass(frozen=True)
class ExperimentSnapshot(ApiModel):
    target_version_id: str = ""
    dataset_version_id: str = ""
    evaluator_version_ids: list[str] = field(default_factory=list)
    policy_version_id: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> ExperimentSnapshot:
        return cls(
            target_version_id=data.get("target_version_id", ""),
            dataset_version_id=data.get("dataset_version_id", ""),
            evaluator_version_ids=data.get("evaluator_version_ids", []) or [],
            policy_version_id=data.get("policy_version_id"),
            settings=data.get("settings", {}) or {},
        )


@dataclass(frozen=True)
class Experiment(ApiModel):
    id: str = ""
    organization_id: str = ""
    project_id: str = ""
    name: str = ""
    status: str = ""
    created_at: datetime | None = None
    clone_of: str | None = None
    snapshot: ExperimentSnapshot | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Experiment:
        return cls(
            id=data.get("id", ""),
            organization_id=data.get("organization_id", ""),
            project_id=data.get("project_id", ""),
            name=data.get("name", ""),
            status=data.get("status", ""),
            created_at=_dt(data.get("created_at")),
            clone_of=data.get("clone_of"),
            snapshot=(
                ExperimentSnapshot.parse(data["snapshot"]) if data.get("snapshot") else None
            ),
        )


@dataclass(frozen=True)
class Run(ApiModel):
    run_id: str = ""
    experiment_id: str = ""
    status: str = ""
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    evidence_summary: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancelled_by: str | None = None
    cancelled_at: datetime | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Run:
        return cls(
            run_id=data.get("run_id", ""),
            experiment_id=data.get("experiment_id", ""),
            status=data.get("status", ""),
            created_at=_dt(data.get("created_at")),
            started_at=_dt(data.get("started_at")),
            finished_at=_dt(data.get("finished_at")),
            evidence_summary=data.get("evidence_summary"),
            error=data.get("error"),
            cancelled_by=data.get("cancelled_by"),
            cancelled_at=_dt(data.get("cancelled_at")),
        )

    @property
    def terminal(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}


@dataclass(frozen=True)
class MetricResult(ApiModel):
    id: str = ""
    run_id: str = ""
    execution_id: str = ""
    metric_name: str = ""
    score: float | None = None
    reason: str | None = None
    severity: str | None = None


@dataclass(frozen=True)
class EvaluatorSpec(ApiModel):
    identity: str = ""
    version: str = ""
    display_name: str = ""
    metrics: list[str] = field(default_factory=list)
    requires_trace: bool = False
    severity: str = "info"
    unit: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> EvaluatorSpec:
        return cls(
            identity=data.get("identity", ""),
            version=data.get("version", ""),
            display_name=data.get("display_name", ""),
            metrics=data.get("metrics", []) or [],
            requires_trace=_bool(data.get("requires_trace")),
            severity=data.get("severity", "info"),
            unit=data.get("unit"),
        )


@dataclass(frozen=True)
class GateDecision(ApiModel):
    gate_id: str = ""
    verdict: str = ""
    reason: str = ""
    severity: str = ""


@dataclass(frozen=True)
class GateReport(ApiModel):
    run_id: str = ""
    verdict: str = ""
    decisions: list[GateDecision] = field(default_factory=list)
    evaluated_at: datetime | None = None
    overridden: bool = False
    override: dict[str, Any] | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> GateReport:
        return cls(
            run_id=data.get("run_id", ""),
            verdict=data.get("verdict", ""),
            decisions=_parse_list(GateDecision, data.get("decisions")),
            evaluated_at=_dt(data.get("evaluated_at")),
            overridden=_bool(data.get("overridden")),
            override=data.get("override"),
        )


@dataclass(frozen=True)
class TrendPoint(ApiModel):
    timestamp: datetime | None = None
    score: float = 0.0
    run_id: str = ""


@dataclass(frozen=True)
class TrendReport(ApiModel):
    metric_name: str = ""
    data_points: list[TrendPoint] = field(default_factory=list)
    overall_trend: str = "stable"
    analyzed_at: datetime | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> TrendReport:
        points = []
        for point in data.get("data_points") or []:
            points.append(
                TrendPoint(
                    timestamp=_dt(point.get("timestamp")),
                    score=float(point.get("score", 0.0)),
                    run_id=point.get("run_id", ""),
                )
            )
        return cls(
            metric_name=data.get("metric_name", ""),
            data_points=points,
            overall_trend=data.get("overall_trend", "stable"),
            analyzed_at=_dt(data.get("analyzed_at")),
        )


@dataclass(frozen=True)
class HealthCheck(ApiModel):
    name: str = ""
    status: str = "unknown"
    detail: str | None = None


@dataclass(frozen=True)
class HealthSummary(ApiModel):
    overall: str = "unknown"
    checks: list[HealthCheck] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> HealthSummary:
        return cls(
            overall=data.get("overall", "unknown"),
            checks=_parse_list(HealthCheck, data.get("checks")),
        )


@dataclass(frozen=True)
class Token(ApiModel):
    token: str = ""
    expires_at: datetime | None = None
    authentication_method: str = "service_account"

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Token:
        return cls(
            token=data.get("token", ""),
            expires_at=_dt(data.get("expires_at")),
            authentication_method=data.get("authentication_method", "service_account"),
        )


__all__ = [
    "ApiModel",
    "CatalogDataset",
    "CatalogSummary",
    "CatalogTarget",
    "EvaluatorSpec",
    "Experiment",
    "ExperimentSnapshot",
    "GateDecision",
    "GateReport",
    "HealthCheck",
    "HealthSummary",
    "MetricResult",
    "Run",
    "Token",
    "TrendPoint",
    "TrendReport",
]