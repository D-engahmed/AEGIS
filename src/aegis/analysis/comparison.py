"""Experiment comparison (A/B): shared metrics, winners, significance."""

from __future__ import annotations

from aegis.domain import MetricResult
from aegis.domain.time import Clock, SystemClock

from .models import ComparisonReport, MetricComparison
from .ports import ExperimentComparator
from .statistics import mean, t_test

_MIN_SAMPLE = 5


class WelchExperimentComparator(ExperimentComparator):
    """Compares two experiments metric-by-metric using Welch's t-test."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()

    def compare(
        self,
        experiment_a_results: list[MetricResult],
        experiment_b_results: list[MetricResult],
    ) -> ComparisonReport:
        if not experiment_a_results or not experiment_b_results:
            raise ValueError("comparison requires results from both experiments")
        experiment_a_id = experiment_a_results[0].run_id
        experiment_b_id = experiment_b_results[0].run_id
        metrics_a: dict[str, list[MetricResult]] = _group_by_metric(experiment_a_results)
        metrics_b: dict[str, list[MetricResult]] = _group_by_metric(experiment_b_results)
        if set(metrics_a) != set(metrics_b):
            missing_a = sorted(set(metrics_b) - set(metrics_a))
            missing_b = sorted(set(metrics_a) - set(metrics_b))
            raise ValueError(
                f"experiments measure different metrics: "
                f"only in A={missing_b}, only in B={missing_a}"
            )

        comparisons: list[MetricComparison] = []
        for metric_name in sorted(metrics_a.keys() & metrics_b.keys()):
            scores_a = [r.score for r in metrics_a[metric_name]]
            scores_b = [r.score for r in metrics_b[metric_name]]
            mean_a, mean_b = mean(scores_a), mean(scores_b)
            significant = False
            p_value: float | None = None
            interval: tuple[float, float] | None = None
            if len(scores_a) >= _MIN_SAMPLE and len(scores_b) >= _MIN_SAMPLE:
                p_value = t_test(scores_a, scores_b)[1]
                significant = p_value < 0.05
            comparisons.append(
                MetricComparison(
                    metric_name=metric_name,
                    mean_a=mean_a,
                    mean_b=mean_b,
                    delta=mean_b - mean_a,
                    is_significant=significant,
                    p_value=p_value,
                    confidence_interval=interval,
                )
            )

        winner = self._overall_winner(comparisons)
        return ComparisonReport(
            experiment_a_id=experiment_a_id,
            experiment_b_id=experiment_b_id,
            metric_comparisons=tuple(comparisons),
            overall_winner=winner,
            analyzed_at=self._clock.now(),
        )

    @staticmethod
    def _overall_winner(comparisons: list[MetricComparison]) -> str | None:
        significant = [c for c in comparisons if c.is_significant]
        if not significant:
            return None
        winning_b = sum(1 for c in significant if c.delta > 0)
        winning_a = len(significant) - winning_b
        if winning_b > winning_a and winning_b > 0:
            return "b"
        if winning_a > winning_b and winning_a > 0:
            return "a"
        return None


def _group_by_metric(results: list[MetricResult]) -> dict[str, list[MetricResult]]:
    grouped: dict[str, list[MetricResult]] = {}
    for result in results:
        grouped.setdefault(result.metric_name, []).append(result)
    return grouped


__all__ = ["WelchExperimentComparator"]
