"""Validation helpers for execution traces before they become evidence."""

from __future__ import annotations

from collections.abc import Iterable

from .models import SpanAttributes, SpanData


def validate_trace(run_id: str, trace_id: str, spans: Iterable[SpanData]) -> None:
    """Reject malformed evidence before evaluation can consume it."""
    if not run_id:
        raise ValueError("run_id is required")
    if not trace_id:
        raise ValueError("trace_id is required")
    items = list(spans)
    if not items:
        raise ValueError("trace must contain at least one span")
    if any(span.trace_id != trace_id for span in items):
        raise ValueError("all spans must belong to the supplied trace_id")

    correlated = [span for span in items if _is_correlated(span)]
    if not correlated:
        raise ValueError("trace has no evaluation correlation")

    run_ids = {
        str(span.attributes[SpanAttributes.RUN_ID])
        for span in correlated
        if span.attributes.get(SpanAttributes.RUN_ID)
    }
    if run_ids and run_ids != {run_id}:
        raise ValueError("trace contains a different run_id")

    execution_ids = {
        str(span.attributes[SpanAttributes.EXECUTION_ID])
        for span in correlated
        if span.attributes.get(SpanAttributes.EXECUTION_ID)
    }
    if len(execution_ids) > 1:
        raise ValueError("a preserved evaluation trace cannot mix execution ids")


def _is_correlated(span: SpanData) -> bool:
    return bool(
        span.attributes.get(SpanAttributes.RUN_ID)
        or span.attributes.get(SpanAttributes.EXECUTION_ID)
    )


__all__ = ["validate_trace"]
