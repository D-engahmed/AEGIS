"""Analysis value objects: statistical reports over metric results.

All reports are frozen (immutable historical records) and carry the evaluator
identity/version they were computed from, so an analysis can always be traced
to the data that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FailureCategory(StrEnum):
    MODEL = "model"
    RETRIEVAL = "retrieval"
    TOOL = "tool"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"


@dataclass(frozen=True)
class RegressionReport:
    metric_name: str
    baseline_score: float
    current_score: float
    delta: float
    is_regression: bool
    confidence_level: float
    is_statistically_significant: bool
    sample_size_baseline: int
    sample_size_current: int
    evaluator_identity: str
    evaluator_version: str
    analyzed_at: datetime


@dataclass(frozen=True)
class FailureClusterReport:
    cluster_id: str
    failure_category: FailureCategory
    count: int
    failure_ids: tuple[str, ...]
    representative_message: str
    severity: str


@dataclass(frozen=True)
class MetricComparison:
    metric_name: str
    mean_a: float
    mean_b: float
    delta: float
    is_significant: bool
    p_value: float | None
    confidence_interval: tuple[float, float] | None


@dataclass(frozen=True)
class ComparisonReport:
    experiment_a_id: str
    experiment_b_id: str
    metric_comparisons: tuple[MetricComparison, ...]
    overall_winner: str | None
    analyzed_at: datetime


@dataclass(frozen=True)
class SliceReport:
    dimension: str
    slice_name: str
    metric_name: str
    mean_score: float
    sample_size: int
    std_dev: float
    regression_from_global: bool


@dataclass(frozen=True)
class TrendPoint:
    timestamp: datetime
    score: float
    run_id: str


@dataclass(frozen=True)
class TrendReport:
    metric_name: str
    data_points: tuple[TrendPoint, ...]
    overall_trend: TrendDirection
    analyzed_at: datetime


__all__ = [
    "ComparisonReport",
    "FailureCategory",
    "FailureClusterReport",
    "MetricComparison",
    "RegressionReport",
    "SliceReport",
    "TrendDirection",
    "TrendPoint",
    "TrendReport",
]
