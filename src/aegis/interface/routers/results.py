"""Metric result mappers (shared by run and analysis routers)."""

from __future__ import annotations

from aegis.domain import MetricResult

from ..schemas import MetricResultOut


def metric_result_out(result: MetricResult) -> MetricResultOut:
    return MetricResultOut(
        id=result.id,
        run_id=result.run_id,
        execution_id=result.execution_id,
        metric_name=result.metric_name,
        score=result.score,
        reason=result.reason,
        severity=result.severity,
    )


__all__ = ["metric_result_out"]
