"""Tracing: span recording, exporting, and evaluation-trace preservation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .models import SpanAttributes, SpanData, SpanStatusCode, TraceRecord
from .preservation import TracePreservationEngine


class TelemetryExporter:
    """Unified export boundary; production swaps in an OTLP exporter."""

    def export_span(self, span_data: SpanData) -> None: ...
    def shutdown(self) -> None: ...


class InMemoryExporter(TelemetryExporter):
    """Collects exported spans for tests and local inspection."""

    def __init__(self) -> None:
        self.spans: list[SpanData] = []

    def export_span(self, span_data: SpanData) -> None:
        self.spans.append(span_data)

    def shutdown(self) -> None:
        self.spans.clear()


@dataclass
class SpanBuilder:
    """Mutable span under construction; end() freezes it into SpanData."""

    trace: InMemoryTracer
    span_id: str
    name: str
    attributes: dict[str, Any]

    def end(
        self,
        start_time: datetime,
        status: SpanStatusCode = SpanStatusCode.OK,
    ) -> SpanData:
        end_time = datetime.now(UTC)
        return self.trace._complete(
            span_id=self.span_id,
            name=self.name,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=dict(self.attributes),
        )


class InMemoryTracer:
    """Records spans into a trace buffer; every span routes through export."""

    def __init__(
        self,
        trace_id: str,
        exporter: TelemetryExporter,
        preservation: TracePreservationEngine,
        project_id: str | None = None,
    ) -> None:
        self.trace_id = trace_id
        self._exporter = exporter
        self._preservation = preservation
        self._project_id = project_id
        self._buffer: list[SpanData] = []
        self._current_parent: str | None = None

    def start_span(self, name: str, **attributes: Any) -> SpanBuilder:
        if self._project_id is not None:
            attributes.setdefault(SpanAttributes.PROJECT_ID, self._project_id)
        return SpanBuilder(
            trace=self,
            span_id=uuid.uuid4().hex[:16],
            name=name,
            attributes=attributes,
        )

    def _complete(
        self,
        span_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        status: SpanStatusCode,
        attributes: dict[str, Any],
    ) -> SpanData:
        span_data = SpanData(
            span_id=span_id,
            name=name,
            trace_id=self.trace_id,
            parent_span_id=self._current_parent,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=attributes,
        )
        self._current_parent = span_id
        self._buffer.append(span_data)
        self._exporter.export_span(span_data)
        return span_data

    def flush(self, run_id: str) -> TraceRecord | None:
        """Preserve the buffer as an evidence trace when it is evaluation-linked."""
        if not self._buffer:
            return None
        record = self._preservation.preserve_evaluation_trace(
            run_id, self.trace_id, list(self._buffer)
        )
        self._buffer.clear()
        return record


class InMemoryTracerProvider:
    """Provides named tracers, each with its own trace id."""

    def __init__(
        self,
        exporter: TelemetryExporter | None = None,
        preservation: TracePreservationEngine | None = None,
        project_id: str | None = None,
    ) -> None:
        self.exporter = exporter or InMemoryExporter()
        self.preservation = preservation or TracePreservationEngine()
        self._project_id = project_id
        self._tracers: dict[str, InMemoryTracer] = {}

    def get_tracer(self, name: str) -> InMemoryTracer:
        """Return a (shared by name) tracer with a stable trace id."""
        if name not in self._tracers:
            self._tracers[name] = InMemoryTracer(
                trace_id=uuid.uuid4().hex,
                exporter=self.exporter,
                preservation=self.preservation,
                project_id=self._project_id,
            )
        return self._tracers[name]


__all__ = [
    "InMemoryExporter",
    "InMemoryTracer",
    "InMemoryTracerProvider",
    "SpanBuilder",
    "SpanData",
    "TelemetryExporter",
]
