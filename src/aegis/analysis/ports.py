"""Analysis ports: the statistical services consumed by dashboards and gates."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aegis.domain import MetricResult

from .models import (
    ComparisonReport,
    FailureClusterReport,
    RegressionReport,
    SliceReport,
    TrendReport,
)


class RegressionDetector(Protocol):
    """Compares current results against a baseline for per-metric regressions."""

    def detect(
        self,
        baseline_results: list[MetricResult],
        current_results: list[MetricResult],
        significance_level: float = 0.05,
    ) -> RegressionReport: ...


class FailureClassifier(Protocol):
    """Groups failed executions into root-cause clusters."""

    def classify(self, failure_results: list[MetricResult]) -> list[FailureClusterReport]: ...


class ExperimentComparator(Protocol):
    """Compares two experiments on shared metrics."""

    def compare(
        self,
        experiment_a_results: list[MetricResult],
        experiment_b_results: list[MetricResult],
    ) -> ComparisonReport: ...


class ResultSlicer(Protocol):
    """Slices results along a dimension supplied by dataset case metadata."""

    def slice_by(
        self,
        results: list[MetricResult],
        dimension: str,
        dimension_map: dict[str, str],
    ) -> list[SliceReport]: ...


class TrendAnalyzer(Protocol):
    """Tracks a metric over time to classify improving/degrading/stable."""

    def analyze(
        self,
        metric_name: str,
        historical_results: list[tuple[datetime, str, list[MetricResult]]],
    ) -> TrendReport: ...


__all__ = [
    "ExperimentComparator",
    "FailureClassifier",
    "RegressionDetector",
    "ResultSlicer",
    "TrendAnalyzer",
]
