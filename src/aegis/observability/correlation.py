"""Correlation id propagation across async boundaries via contextvars."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_correlation_id_var: ContextVar[str] = ContextVar("aegis_correlation_id", default="")


class CorrelationContext:
    """Bind and read the current request/job correlation id."""

    @staticmethod
    def new() -> str:
        """Generate a fresh correlation id and bind it for this context."""
        value = uuid.uuid4().hex
        return CorrelationContext.bind(value)

    @staticmethod
    def bind(correlation_id: str) -> str:
        """Set the correlation id for the current async context."""
        _correlation_id_var.set(correlation_id)
        return correlation_id

    @staticmethod
    def get() -> str:
        """Return the current correlation id ('' when unset)."""
        return _correlation_id_var.get()


__all__ = ["CorrelationContext"]
