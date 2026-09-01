"""Run-tracer adapter: bridges the engine to the OTel span model and preservation.

Implements the application-layer RunTracer/RunSpan protocols over the existing
observability tracer, wiring evaluation spans into the never-sampled preservation
engine so every execution's trace becomes evidence (evidence-architecture.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis.application.run_tracing import RunSpan, RunTracer, RunTracerProvider
from aegis.observability.models import SpanAttributes, SpanStatusCode
from aegis.observability.preservation import TracePreservationEngine
from aegis.observability.tracing import InMemoryTracer, InMemoryTracerProvider


class EvaluationRunSpan(RunSpan):
    """Wraps a SpanBuilder, setting AEGIS correlation attributes on it."""

    def __init__(self, builder, run_id: str, execution_id: str) -> None:
        self._builder = builder
        self._started = datetime.now(UTC)
        self._run_id = run_id
        self._execution_id = execution_id
        builder.attributes.setdefault(SpanAttributes.RUN_ID, run_id)
        builder.attributes.setdefault(SpanAttributes.EXECUTION_ID, execution_id)

    def set_attribute(self, key: str, value: object) -> None:
        self._builder.attributes[key] = value

    def end(self, status_code: str = "ok") -> None:
        self._builder.end(
            start_time=self._started,
            status=SpanStatusCode(status_code),
        )


class EvaluationRunTracer(RunTracer):
    """Per-run tracer over the observability in-memory tracer."""

    def __init__(self, tracer: InMemoryTracer) -> None:
        self._tracer = tracer
        self._execution: str | None = None

    def start_span(self, name: str, **attributes: object) -> RunSpan:
        aliases = {
            "run_id": SpanAttributes.RUN_ID,
            "execution_id": SpanAttributes.EXECUTION_ID,
        }
        for alias, canonical in aliases.items():
            if alias in attributes:
                attributes.setdefault(canonical, attributes[alias])
        builder = self._tracer.start_span(name)
        for key, value in attributes.items():
            builder.attributes[key] = value
        run_id = str(builder.attributes.get(SpanAttributes.RUN_ID, ""))
        execution = self._execution or ""
        execution_id = str(builder.attributes.get(SpanAttributes.EXECUTION_ID, execution))
        return EvaluationRunSpan(builder, run_id=run_id, execution_id=execution_id)

    def set_execution(self, execution_id: str) -> None:
        self._execution = execution_id

    def flush(self, run_id: str) -> str | None:
        if not self._tracer._buffer:
            return None
        record = self._tracer.flush(run_id)
        return record.trace_id if record is not None else None


class EvaluationTracerProvider(RunTracerProvider):
    """Provides per-run tracers backed by the in-memory observability tracer."""

    def __init__(
        self,
        preservation: TracePreservationEngine | None = None,
    ) -> None:
        self._preservation = preservation or TracePreservationEngine()
        self._provider = InMemoryTracerProvider(preservation=self._preservation)

    def get_tracer(self, name: str) -> RunTracer:
        return EvaluationRunTracer(self._provider.get_tracer(name))

    def preservation(self):
        return self._preservation


class _InMemoryRunSpan:
    """Lightweight span used when no real tracer is injected (no-op path)."""

    def __init__(self, name: str, run_id: str, execution_id: str) -> None:
        self._started = datetime.now(UTC)
        self._name = name
        self._run_id = run_id
        self._execution_id = execution_id
        self._attributes: dict[str, Any] = {
            SpanAttributes.RUN_ID: run_id,
            SpanAttributes.EXECUTION_ID: execution_id,
        }

    def set_attribute(self, key: str, value: object) -> None:
        self._attributes[key] = value

    def end(self, status_code: str = "ok") -> None:
        return None


class _NoopRunTracer(RunTracer):
    """Does nothing; the engine strips spans without a configured provider."""

    def start_span(self, name: str, **attributes: object) -> RunSpan:
        return _InMemoryRunSpan(name, "", "")

    def flush(self, run_id: str) -> str | None:
        return None


_NOOP = _NoopRunTracer()


class _UnitRunSpan(RunSpan):
    """Injectable span for deterministic verification of engine wiring."""

    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.ended = False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def end(self, status_code: str = "ok") -> None:
        self.ended = True


class RecordingRunTracer(RunTracer):
    """A scripted tracer for tests: records spans and flushes nothing."""

    def __init__(self) -> None:
        self.spans: list[_UnitRunSpan] = []
        self.flushed: list[str] = []

    def start_span(self, name: str, **attributes: object) -> RunSpan:
        span = _UnitRunSpan()
        span.attributes.update(attributes)
        self.spans.append(span)
        return span

    def flush(self, run_id: str) -> str | None:
        self.flushed.append(run_id)
        return f"trace-{run_id}"


def noop_tracer() -> RunTracer:
    """Return the shared no-op tracer for engine default wiring."""
    return _NOOP


__all__ = [
    "EvaluationRunSpan",
    "EvaluationRunTracer",
    "EvaluationTracerProvider",
    "RecordingRunTracer",
    "noop_tracer",
]
