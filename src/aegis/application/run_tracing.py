"""Run tracing ports: a tracer/span surface the engine spawns per execution.

The execution layer depends only on these protocols so production can swap in
an OpenTelemetry implementation without touching the engine (ADR-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TraceSpanPayload:
    """Serialized span shape shared by tracing and persistence adapters."""

    span_id: str
    name: str
    trace_id: str
    parent_span_id: str | None
    start_time: datetime
    end_time: datetime
    status: str
    attributes: dict[str, object]


@dataclass(frozen=True)
class TracePayload:
    """Portable trace record that does not couple the application port to OTel."""

    trace_id: str
    run_id: str
    execution_id: str | None
    preserved_at: datetime
    spans: tuple[TraceSpanPayload, ...]


@runtime_checkable
class TraceStore(Protocol):
    """Durable/read-through storage contract for preserved evaluation traces."""

    def persist(self, trace: TracePayload) -> None: ...
    def list_for_run(self, run_id: str) -> list[TracePayload]: ...
    def list_for_execution(self, execution_id: str) -> list[TracePayload]: ...


@runtime_checkable
class RunSpan(Protocol):
    """An in-flight span recording an execution's duration and attributes."""

    def set_attribute(self, key: str, value: object) -> None: ...

    def end(self, status_code: str = "ok") -> None: ...


@runtime_checkable
class RunTracer(Protocol):
    """A per-run tracer that starts spans and can flush a preserved trace."""

    @property
    def trace_id(self) -> str | None: ...

    def start_span(self, name: str, **attributes: object) -> RunSpan: ...

    def flush(self, run_id: str) -> str | None:
        """Persist the run's spans; returns the preserved trace id, if any."""
        ...


@runtime_checkable
class RunTracerProvider(Protocol):
    """Provides a named tracer; implementations carry a stable trace id."""

    def get_tracer(self, name: str) -> RunTracer: ...


__all__ = [
    "RunSpan",
    "RunTracer",
    "RunTracerProvider",
    "TracePayload",
    "TraceSpanPayload",
    "TraceStore",
]
