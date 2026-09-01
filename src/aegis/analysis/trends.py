"""Trend analysis: classifies a metric's trajectory as improving/degrading/stable."""

from __future__ import annotations

from datetime import datetime
from statistics import mean

from aegis.domain import MetricResult
from aegis.domain.time import Clock, SystemClock

from .models import TrendDirection, TrendPoint, TrendReport
from .ports import TrendAnalyzer

_STABLE_TOLERANCE = 0.02
_MIN_POINTS = 3


class LinearTrendAnalyzer(TrendAnalyzer):
    """Classifies the trend from the slope of a least-squares fit."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()

    def analyze(
        self,
        metric_name: str,
        historical_results: list[tuple[datetime, str, list[MetricResult]]],
    ) -> TrendReport:
        points: list[TrendPoint] = []
        for timestamp, run_id, results in historical_results:
            scores = [r.score for r in results if r.metric_name == metric_name]
            if not scores:
                continue
            points.append(TrendPoint(timestamp=timestamp, score=mean(scores), run_id=run_id))
        overall = TrendDirection.STABLE if len(points) < _MIN_POINTS else _slope_direction(points)
        return TrendReport(
            metric_name=metric_name,
            data_points=tuple(points),
            overall_trend=overall,
            analyzed_at=self._clock.now(),
        )


def _slope_direction(points: list[TrendPoint]) -> TrendDirection:
    x = [point.timestamp.timestamp() for point in points]
    y = [point.score for point in points]
    slope = _least_squares_slope(x, y)
    normalized = slope * (max(x) - min(x)) / (mean(y) or 1.0)
    if normalized > _STABLE_TOLERANCE:
        return TrendDirection.IMPROVING
    if normalized < -_STABLE_TOLERANCE:
        return TrendDirection.DEGRADING
    return TrendDirection.STABLE


def _least_squares_slope(x: list[float], y: list[float]) -> float:
    mean_x = mean(x)
    mean_y = mean(y)
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=True))
    denominator = sum((xi - mean_x) ** 2 for xi in x)
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


__all__ = ["LinearTrendAnalyzer"]
