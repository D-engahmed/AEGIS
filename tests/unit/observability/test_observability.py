"""Observability layer (10): health, cost, tracing, preservation, logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from aegis.observability.correlation import CorrelationContext
from aegis.observability.cost import InMemoryCostTracker
from aegis.observability.health import HealthAggregator, StaticHealthCheck
from aegis.observability.logging import CorrelationJsonFormatter
from aegis.observability.models import (
    HealthStatus,
    SpanAttributes,
    SpanData,
    SpanStatusCode,
)
from aegis.observability.preservation import TracePreservationEngine
from aegis.observability.tracing import (
    InMemoryExporter,
    InMemoryTracerProvider,
)

pytestmark = pytest.mark.unit


def _evaluation_span(span_id="span:1", name="evaluate") -> SpanData:
    return SpanData(
        span_id=span_id,
        name=name,
        trace_id="trace:1",
        parent_span_id=None,
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC),
        status=SpanStatusCode.OK,
        attributes={
            SpanAttributes.RUN_ID: "run:1",
            SpanAttributes.EXECUTION_ID: "exe:1",
        },
    )


def _operational_span() -> SpanData:
    return SpanData(
        span_id="span:2",
        name="http-request",
        trace_id="trace:2",
        parent_span_id=None,
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC),
        attributes={"aegis.route": "/health"},
    )


def test_health_aggregator_worst_wins():
    aggregator = HealthAggregator(
        [
            StaticHealthCheck("a", HealthStatus.HEALTHY, "ok"),
            StaticHealthCheck("b", HealthStatus.DEGRADED, "slow"),
        ]
    )
    checks = aggregator.aggregate()
    assert checks["a"] == "healthy"
    assert checks["b"] == "degraded"
    assert not aggregator.is_healthy()


def test_health_aggregator_all_healthy():
    aggregator = HealthAggregator(
        [StaticHealthCheck("a", HealthStatus.HEALTHY), StaticHealthCheck("b", HealthStatus.HEALTHY)]
    )
    assert aggregator.is_healthy()
    assert set(aggregator.aggregate()) == {"a", "b"}


def test_cost_tracker_separates_target_and_evaluator():
    tracker = InMemoryCostTracker()
    tracker.record_target_cost("run:1", 1.5)
    tracker.record_evaluator_cost("run:1", 0.5)
    tracker.record_target_cost("run:1", 0.25)
    assert tracker.target_cost("run:1") == pytest.approx(1.75)
    assert tracker.evaluator_cost("run:1") == pytest.approx(0.5)
    assert tracker.total_cost("run:1") == pytest.approx(2.25)
    assert tracker.total_cost("run:missing") == 0.0


def test_cost_tracker_forwards_metrics():
    seen: list[tuple[str, str, float]] = []

    def sink(run_id: str, metric: str, value: float) -> None:
        seen.append((run_id, metric, value))

    tracker = InMemoryCostTracker(on_metric=sink)
    tracker.record_target_cost("run:1", 2.0)
    assert len(seen) == 1
    assert seen[0][0] == "run:1"
    assert "cost_usd" in seen[0][1]


def test_tracer_records_and_exports_spans():
    exporter = InMemoryExporter()
    provider = InMemoryTracerProvider(exporter)
    tracer = provider.get_tracer("experiments")
    builder = tracer.start_span("invoke", **{SpanAttributes.EXPERIMENT_ID: "exp:1"})
    builder.end(datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC))
    assert len(exporter.spans) == 1
    assert exporter.spans[0].name == "invoke"
    assert exporter.spans[0].attributes[SpanAttributes.EXPERIMENT_ID] == "exp:1"


def test_tracer_flush_preserves_evaluation_trace():
    provider = InMemoryTracerProvider()
    tracer = provider.get_tracer("evaluation")
    builder = tracer.start_span(
        "score",
        **{
            SpanAttributes.RUN_ID: "run:1",
            SpanAttributes.EXECUTION_ID: "exe:1",
        },
    )
    builder.end(datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC))
    record = tracer.flush("run:1")
    assert record is not None
    assert record.trace_id == tracer.trace_id
    assert record.run_id == "run:1"
    assert record.execution_id == "exe:1"
    assert len(provider.preservation.traces_for_run("run:1")) == 1


def test_evaluation_span_never_sampled():
    engine = TracePreservationEngine()
    assert engine.is_evaluation_span(_evaluation_span())
    assert engine.should_sample(_evaluation_span(), sample_rate=0.0) is False


def test_operational_span_honors_sample_rate():
    engine = TracePreservationEngine()
    span = _operational_span()
    assert not engine.is_evaluation_span(span)
    assert engine.should_sample(span, sample_rate=1.0) is True


def test_preservation_tracks_runs_and_executions():
    engine = TracePreservationEngine()
    engine.preserve_evaluation_trace("run:1", "trace:1", [_evaluation_span()])
    assert len(engine.traces_for_run("run:1")) == 1
    assert len(engine.traces_for_execution("exe:1")) == 1
    assert engine.traces_for_run("run:missing") == []


def test_correlation_context_binds_and_reads():
    CorrelationContext.bind("corr:alpha")
    assert CorrelationContext.get() == "corr:alpha"
    CorrelationContext.bind("corr:beta")
    assert CorrelationContext.get() == "corr:beta"


def test_correlation_context_default_empty():
    CorrelationContext.bind("")
    assert CorrelationContext.get() == ""


def test_json_formatter_includes_correlation_and_extra():
    CorrelationContext.bind("corr:42")
    formatter = CorrelationJsonFormatter()
    record = logging.LogRecord(
        name="aegis.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.aegis_extra = {"run_id": "run:1"}
    payload = json.loads(formatter.format(record))
    assert payload["correlation_id"] == "corr:42"
    assert payload["run_id"] == "run:1"
    assert payload["service"] == "aegis"
    assert payload["message"] == "hello"


def test_exporter_shutdown_clears():
    exporter = InMemoryExporter()
    exporter.export_span(_operational_span())
    assert len(exporter.spans) == 1
    exporter.shutdown()
    assert exporter.spans == []


__all__ = []
