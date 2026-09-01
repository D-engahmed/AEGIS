"""Run tracing ports: a tracer/span surface the engine spawns per execution.

The execution layer depends only on these protocols so production can swap in
an OpenTelemetry implementation without touching the engine (ADR-005).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RunSpan(Protocol):
    """An in-flight span recording an execution's duration and attributes."""

    def set_attribute(self, key: str, value: object) -> None: ...

    def end(self, status_code: str = "ok") -> None: ...


@runtime_checkable
class RunTracer(Protocol):
    """A per-run tracer that starts spans and can flush a preserved trace."""

    def start_span(self, name: str, **attributes: object) -> RunSpan: ...

    def flush(self, run_id: str) -> str | None:
        """Persist the run's spans; returns the preserved trace id, if any."""
        ...


@runtime_checkable
class RunTracerProvider(Protocol):
    """Provides a named tracer; implementations carry a stable trace id."""

    def get_tracer(self, name: str) -> RunTracer: ...


__all__ = ["RunSpan", "RunTracer", "RunTracerProvider"]
