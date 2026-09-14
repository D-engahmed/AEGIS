"""Observability mappers: health, cost, and trace shapes.

Health has a wire schema; cost and traces are intentionally untyped wire
dicts (see routers/observability.py) — the mappers centralize their
assembly so the shape lives in one place.
"""

from __future__ import annotations

from ..schemas import HealthCheckOut, HealthSummaryOut


def health_summary_out(checks: dict, is_healthy: bool) -> HealthSummaryOut:
    return HealthSummaryOut(
        overall="healthy" if is_healthy else "unhealthy",
        checks=[
            HealthCheckOut(name=name, status=status_value) for name, status_value in checks.items()
        ],
    )


def cost_out(total_usd: float, target_usd: float, evaluator_usd: float) -> dict[str, float]:
    return {
        "total_usd": total_usd,
        "target_usd": target_usd,
        "evaluator_usd": evaluator_usd,
    }


def span_out(span) -> dict[str, object]:
    return {
        "span_id": span.span_id,
        "name": span.name,
        "status": span.status.value,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "attributes": dict(span.attributes),
    }


def trace_out(trace) -> dict[str, object]:
    return {
        "trace_id": trace.trace_id,
        "run_id": trace.run_id,
        "execution_id": trace.execution_id,
        "span_count": len(trace.spans),
        "preserved_at": trace.preserved_at,
        "spans": [span_out(s) for s in trace.spans],
    }


__all__ = ["cost_out", "health_summary_out", "span_out", "trace_out"]
