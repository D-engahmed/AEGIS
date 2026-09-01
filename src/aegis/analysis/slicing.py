"""Result slicing: breaks a metric down along a dataset dimension."""

from __future__ import annotations

from statistics import mean, stdev

from aegis.domain import MetricResult

from .models import SliceReport
from .ports import ResultSlicer


class DimensionSlicer(ResultSlicer):
    """Slices results per dimension value and flags slices below the global mean."""

    def slice_by(
        self,
        results: list[MetricResult],
        dimension: str,
        dimension_map: dict[str, str],
    ) -> list[SliceReport]:
        if not results:
            return []
        metric_name = _require_single_metric(results)
        global_scores = [r.score for r in results]
        global_mean = mean(global_scores)

        buckets: dict[str, list[MetricResult]] = {}
        for result in results:
            slice_name = dimension_map.get(result.test_case_id, "unknown")
            buckets.setdefault(slice_name, []).append(result)

        reports: list[SliceReport] = []
        for slice_name in sorted(buckets):
            scores = [r.score for r in buckets[slice_name]]
            std = stdev(scores) if len(scores) > 1 else 0.0
            slice_mean = mean(scores)
            reports.append(
                SliceReport(
                    dimension=dimension,
                    slice_name=slice_name,
                    metric_name=metric_name,
                    mean_score=slice_mean,
                    sample_size=len(scores),
                    std_dev=std,
                    regression_from_global=slice_mean < global_mean,
                )
            )
        return reports


def _require_single_metric(results: list[MetricResult]) -> str:
    metrics = {r.metric_name for r in results}
    if len(metrics) != 1:
        raise ValueError(f"slicing requires a single metric, got {sorted(metrics)}")
    return next(iter(metrics))


__all__ = ["DimensionSlicer"]
