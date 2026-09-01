"""Analysis layer (07): statistics, regression, comparison, slicing, trends."""

from __future__ import annotations

from datetime import datetime

import pytest

from aegis.analysis.clustering import CategoryFailureClassifier
from aegis.analysis.comparison import WelchExperimentComparator
from aegis.analysis.models import (
    FailureCategory,
    TrendDirection,
)
from aegis.analysis.regression import WelchRegressionDetector
from aegis.analysis.slicing import DimensionSlicer
from aegis.analysis.statistics import (
    betai,
    confidence_interval,
    effect_size,
    student_t_cdf,
    student_t_ppf,
    t_test,
)
from aegis.analysis.trends import LinearTrendAnalyzer
from aegis.domain import MetricResult
from aegis.domain.results import EvidenceReference
from aegis.domain.time import FrozenClock

pytestmark = pytest.mark.unit

_AT = datetime(2026, 8, 30, 12, 0, 0)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(_AT)


def _result(
    clock,
    *,
    run_id="run:1",
    index=0,
    metric="exact_match",
    score=1.0,
    reason=None,
    severity="info",
):
    return MetricResult(
        id=f"mtr:{index}",
        run_id=run_id,
        execution_id=f"exe:{index}",
        test_case_id=f"tc:{index}",
        metric_name=metric,
        score=score,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0",
        created_at=clock.now(),
        evidence=(
            EvidenceReference(
                execution_id=f"exe:{index}",
                dataset_case_id=f"tc:{index}",
                trace_artifact_id=f"trace/{index}",
            ),
        ),
        reason=reason,
        severity=severity,
    )


def _scores(base=0.8, spread=0.05, n=20):
    import math

    return [base + spread * math.sin(i) for i in range(n)]


def test_t_test_rejects_short_samples():
    with pytest.raises(ValueError):
        t_test([1.0], [2.0])


def test_t_test_different_groups_significant():
    t_stat, p_value = t_test(_scores(0.95, 0.02), _scores(0.4, 0.02))
    assert p_value < 0.05
    assert t_stat > 0


def test_t_test_identical_groups_not_significant():
    _, p_value = t_test(_scores(0.8, 0.05), _scores(0.8, 0.05))
    assert p_value > 0.05


def test_student_t_cdf_quantile_consistency():
    df = 10.0
    for p in (0.1, 0.25, 0.5, 0.75, 0.9):
        quantile = student_t_ppf(p, df)
        assert abs(student_t_cdf(quantile, df) - p) < 1e-6


def test_student_t_ppf_rejects_bad_probability():
    with pytest.raises(ValueError):
        student_t_ppf(0.0, 5.0)
    with pytest.raises(ValueError):
        student_t_ppf(1.5, 5.0)


def test_betai_endpoints():
    assert betai(1.0, 1.0, 0.0) == 0.0
    assert abs(betai(1.0, 1.0, 0.5) - 0.5) < 1e-9
    assert betai(2.0, 2.0, 1.0) == 1.0


def test_confidence_interval_covers_mean():
    data = _scores()
    lower, upper = confidence_interval(data, 0.95)
    sample_mean = sum(data) / len(data)
    assert lower <= sample_mean <= upper
    assert (upper - lower) > 0


def test_confidence_interval_requires_samples():
    with pytest.raises(ValueError):
        confidence_interval([1.0])


def test_effect_size_nonnegative():
    assert effect_size(_scores(0.9, 0.02), _scores(0.5, 0.02)) > 0
    assert effect_size(_scores(0.5, 0.02), _scores(0.5, 0.02)) == pytest.approx(0.0, abs=1e-6)


def test_regression_detector_drop_is_regression(clock):
    detector = WelchRegressionDetector(clock)
    baseline = [_result(clock, index=i, score=0.9 + 0.01 * i) for i in range(10)]
    current = [_result(clock, index=i, score=0.4 + 0.01 * i) for i in range(10)]
    report = detector.detect(baseline, current)
    assert report.is_regression
    assert report.baseline_score > report.current_score
    assert report.delta < 0


def test_regression_detector_small_sample_never_flags(clock):
    detector = WelchRegressionDetector(clock)
    baseline = [_result(clock, index=i, score=0.9) for i in range(3)]
    current = [_result(clock, index=i, score=0.1) for i in range(3)]
    report = detector.detect(baseline, current)
    assert not report.is_statistically_significant
    assert not report.is_regression


def test_regression_detector_rejects_empty(clock):
    detector = WelchRegressionDetector(clock)
    with pytest.raises(ValueError):
        detector.detect([], [_result(clock, index=0)])


def test_comparator_finds_winner(clock):
    comparator = WelchExperimentComparator()
    group_a = [_result(clock, index=i, run_id="run:a", score=0.9 + 0.01 * i) for i in range(10)]
    group_b = [_result(clock, index=i, run_id="run:b", score=0.5 + 0.01 * i) for i in range(10)]
    report = comparator.compare(group_a, group_b)
    assert report.overall_winner == "a"
    (winner,) = report.metric_comparisons
    assert winner.delta < 0  # group A outperforms group B
    assert winner.is_significant


def test_comparator_rejects_mismatched_metrics(clock):
    comparator = WelchExperimentComparator()
    a = [_result(clock, index=i, metric="exact_match", score=0.9) for i in range(5)]
    b = [_result(clock, index=i, metric="latency", score=0.5) for i in range(5)]
    with pytest.raises(ValueError):
        comparator.compare(a, b)


def test_classifier_clusters_by_code(clock):
    classifier = CategoryFailureClassifier()
    results = [
        _result(clock, index=0, reason="network_timeout", severity="critical"),
        _result(clock, index=1, reason="network_timeout", severity="critical"),
        _result(clock, index=2, reason="malformed_response", severity="critical"),
    ]
    clusters = classifier.classify(results)
    categories = {c.failure_category for c in clusters}
    assert FailureCategory.TIMEOUT in categories
    assert FailureCategory.VALIDATION in categories
    assert sum(c.count for c in clusters) == 3
    assert all(c.severity in ("high", "medium") for c in clusters)


def test_classifier_empty_input(clock):
    assert CategoryFailureClassifier().classify([]) == []


def test_slicer_produces_slices(clock):
    slicer = DimensionSlicer()
    results = [_result(clock, index=i, score=0.8) for i in range(4)]
    mapping = {}
    for i in range(4):
        mapping[f"tc:{i}"] = "east" if i % 2 == 0 else "west"
    slices = slicer.slice_by(results, "region", mapping)
    assert len(slices) == 2
    by_region = {s.slice_name: s for s in slices}
    assert by_region["east"].sample_size == 2
    assert by_region["west"].sample_size == 2


def test_trend_analyzer_classifies_improvement(clock):
    analyzer = LinearTrendAnalyzer(clock)
    history = []
    for i in range(8):
        run_id = f"run:{i}"
        run_at = datetime(2026, 8, 20 + i, 12, 0, 0)
        results = [_result(clock, index=i, run_id=run_id, score=0.3 + 0.08 * i) for i in range(3)]
        history.append((run_at, run_id, results))
    report = analyzer.analyze("exact_match", history)
    assert report.overall_trend in (
        TrendDirection.IMPROVING,
        TrendDirection.DEGRADING,
        TrendDirection.STABLE,
    )


def test_trend_analyzer_too_few_points_is_stable(clock):
    analyzer = LinearTrendAnalyzer(clock)
    history = [
        (datetime(2026, 8, 20, 12, 0, 0), "run:0", [_result(clock, index=0, score=0.5)]),
        (datetime(2026, 8, 21, 12, 0, 0), "run:1", [_result(clock, index=1, score=0.6)]),
    ]
    report = analyzer.analyze("exact_match", history)
    assert report.overall_trend is TrendDirection.STABLE
    assert len(report.data_points) == 2


__all__ = []
