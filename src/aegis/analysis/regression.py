"""Regression detection: current run vs. a baseline on shared metrics."""

from __future__ import annotations

from aegis.domain import MetricResult
from aegis.domain.time import Clock, SystemClock

from .models import RegressionReport
from .ports import RegressionDetector
from .statistics import mean, t_test

_MIN_SAMPLE = 5


class WelchRegressionDetector(RegressionDetector):
    """Flags a metric as a regression when the drop is statistically significant."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()

    def detect(
        self,
        baseline_results: list[MetricResult],
        current_results: list[MetricResult],
        significance_level: float = 0.05,
    ) -> RegressionReport:
        if not baseline_results or not current_results:
            raise ValueError("regression detection requires both baseline and current results")
        metric_name = self._single_metric(baseline_results + current_results)
        baseline_scores = [r.score for r in baseline_results]
        current_scores = [r.score for r in current_results]
        baseline_mean = mean(baseline_scores)
        current_mean = mean(current_scores)
        sample_ok = len(baseline_scores) >= _MIN_SAMPLE and len(current_scores) >= _MIN_SAMPLE
        significant = False
        if sample_ok:
            p_value = t_test(baseline_scores, current_scores)[1]
            significant = p_value < significance_level
        evaluator = current_results[0]
        return RegressionReport(
            metric_name=metric_name,
            baseline_score=baseline_mean,
            current_score=current_mean,
            delta=current_mean - baseline_mean,
            is_regression=significant and current_mean < baseline_mean,
            confidence_level=1.0 - significance_level,
            is_statistically_significant=significant,
            sample_size_baseline=len(baseline_scores),
            sample_size_current=len(current_scores),
            evaluator_identity=evaluator.evaluator_identity,
            evaluator_version=evaluator.evaluator_version,
            analyzed_at=self._clock.now(),
        )

    @staticmethod
    def _single_metric(results: list[MetricResult]) -> str:
        metrics = {r.metric_name for r in results}
        if len(metrics) != 1:
            raise ValueError(f"analysis requires a single metric, got {sorted(metrics)}")
        return next(iter(metrics))


__all__ = ["WelchRegressionDetector"]
