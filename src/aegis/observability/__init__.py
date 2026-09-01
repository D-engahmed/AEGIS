"""Observability layer (layer 10): telemetry, health, cost, preservation.

Evaluation traces are evidence and are never sampled away
(TracePreservationEngine); operational spans may be sampled. Exporters are
pluggable over the TelemetryExporter boundary — in-memory today, OTLP writers
can use the same API later.
"""

from .correlation import CorrelationContext
from .cost import CostTracker, InMemoryCostTracker
from .health import HealthAggregator, HealthCheck, StaticHealthCheck
from .logging import CorrelationJsonFormatter, get_logger
from .models import (
    HealthStatus,
    MetricDefinitions,
    SpanAttributes,
    SpanData,
    SpanStatusCode,
    TraceRecord,
)
from .preservation import TracePreservationEngine
from .tracing import (
    InMemoryExporter,
    InMemoryTracer,
    InMemoryTracerProvider,
    SpanBuilder,
    TelemetryExporter,
)

__all__ = [
    "CorrelationContext",
    "CorrelationJsonFormatter",
    "CostTracker",
    "HealthAggregator",
    "HealthCheck",
    "HealthStatus",
    "InMemoryCostTracker",
    "InMemoryExporter",
    "InMemoryTracer",
    "InMemoryTracerProvider",
    "MetricDefinitions",
    "SpanAttributes",
    "SpanBuilder",
    "SpanData",
    "SpanStatusCode",
    "StaticHealthCheck",
    "TelemetryExporter",
    "TracePreservationEngine",
    "TraceRecord",
    "get_logger",
]
