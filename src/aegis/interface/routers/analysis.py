"""Analysis endpoints: trends, regressions, comparisons, and failure clusters."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aegis.domain import MetricResult
from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..schemas import TrendPointOut, TrendReportOut

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _load_metric_results(container: Container, run_ids: list[str]) -> list[MetricResult]:
    results: list[MetricResult] = []
    for run_id in run_ids:
        results.extend(container.results.list_for_run(run_id))
    return results


@router.get("/trend/{metric_name}", response_model=TrendReportOut)
def analyze_trend(
    metric_name: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    run_ids: Annotated[list[str] | None, Query()] = None,
) -> TrendReportOut:
    """Evaluate a metric's trajectory over the supplied runs (newest-last)."""
    actor.organization.require_membership(actor.context.user_id)
    runs = run_ids or []
    historical: list[tuple[datetime, str, list[MetricResult]]] = []
    for run_id in runs:
        run = container.runs.load(run_id)
        historical.append((run.created_at, run_id, container.results.list_for_run(run_id)))
    report = container.trends.analyze(metric_name, historical)
    return TrendReportOut(
        metric_name=report.metric_name,
        data_points=[
            TrendPointOut(timestamp=p.timestamp, score=p.score, run_id=p.run_id)
            for p in report.data_points
        ],
        overall_trend=report.overall_trend.value,
        analyzed_at=report.analyzed_at,
    )


@router.get("/regression")
def detect_regression(
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    baseline_run_id: str = Query(...),
    current_run_id: str = Query(...),
    significance_level: float = 0.05,
) -> object:
    """Detect statistically significant per-metric regressions between two runs."""
    actor.organization.require_membership(actor.context.user_id)
    baseline = container.results.list_for_run(baseline_run_id)
    current = container.results.list_for_run(current_run_id)
    try:
        report = container.regression.detect(baseline, current, significance_level)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return report


@router.get("/compare")
def compare_experiments(
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    run_ids_a: Annotated[list[str] | None, Query()] = None,
    run_ids_b: Annotated[list[str] | None, Query()] = None,
) -> object:
    """Compare two groups of runs on shared metrics (Welch's t-test)."""
    actor.organization.require_membership(actor.context.user_id)
    results_a = _load_metric_results(container, run_ids_a or [])
    results_b = _load_metric_results(container, run_ids_b or [])
    try:
        return container.comparator.compare(results_a, results_b)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/failures")
def failure_clusters(
    actor: Annotated[Actor, Depends(require_permission(Permission.RESULT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    run_ids: Annotated[list[str] | None, Query()] = None,
) -> object:
    """Cluster failed scores into root-cause categories for the given runs."""
    actor.organization.require_membership(actor.context.user_id)
    results = _load_metric_results(container, run_ids or [])
    failed = [r for r in results if r.score is not None and r.severity == "critical"]
    return container.failure_classifier.classify(failed)


__all__ = ["router"]
