"""Observability foundation: span/trace records, health, and constants.

Kept dependency-light so the package deploys anywhere; exporters (OTLP later)
implement the TelemetryExporter protocol. Evaluation traces are evidence and are
preserved — never sampled away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class SpanStatusCode(StrEnum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class SpanData:
    """One span as exported; attributes carry AEGIS correlation keys."""

    span_id: str
    name: str
    trace_id: str
    parent_span_id: str | None
    start_time: datetime
    end_time: datetime
    status: SpanStatusCode = SpanStatusCode.OK
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    run_id: str
    execution_id: str | None
    spans: tuple[SpanData, ...]
    preserved_at: datetime


class SpanAttributes:
    """AI telemetry attribute keys shared across exporters and dashboards."""

    SERVICE_NAME = "aegis"
    ORGANIZATION_ID = "aegis.organization.id"
    PROJECT_ID = "aegis.project.id"
    EXPERIMENT_ID = "aegis.experiment.id"
    RUN_ID = "aegis.run.id"
    EXECUTION_ID = "aegis.execution.id"
    TARGET_VERSION_ID = "aegis.target.version.id"
    DATASET_VERSION_ID = "aegis.dataset.version.id"
    EVALUATOR_IDENTITY = "aegis.evaluator.identity"
    EVALUATOR_VERSION = "aegis.evaluator.version"
    METRIC_NAME = "aegis.metric.name"
    COST_USD = "aegis.cost.usd"
    LATENCY_MS = "aegis.latency.ms"


class MetricDefinitions:
    """Named metrics tracked by AEGIS (dashboards depend on these names)."""

    RUN_DURATION_SECONDS = "aegis.run.duration_seconds"
    EXECUTION_DURATION_SECONDS = "aegis.execution.duration_seconds"
    EXECUTION_SUCCESS_TOTAL = "aegis.execution.success_total"
    EXECUTION_FAILURE_TOTAL = "aegis.execution.failure_total"
    RETRY_TOTAL = "aegis.execution.retry_total"
    QUEUE_DEPTH = "aegis.queue.depth"
    WORKER_LATENCY_SECONDS = "aegis.worker.latency_seconds"
    EVALUATOR_DURATION_SECONDS = "aegis.evaluator.duration_seconds"
    TARGET_COST_USD = "aegis.target.cost_usd"
    EVALUATOR_COST_USD = "aegis.evaluator.cost_usd"


__all__ = [
    "HealthStatus",
    "MetricDefinitions",
    "SpanAttributes",
    "SpanData",
    "SpanStatusCode",
    "TraceRecord",
]
