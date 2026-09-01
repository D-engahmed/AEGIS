"""Analysis layer (layer 07): statistics and reports over metric results.

Consumed by dashboards (interface) and gate decisions (policy). Pure-Python
statistics keep the layer dependency-light; the ports allow swapping in scipy
or a service-hosted computation without changing consumers.
"""

from .clustering import CategoryFailureClassifier
from .comparison import WelchExperimentComparator
from .models import (
    ComparisonReport,
    FailureCategory,
    FailureClusterReport,
    MetricComparison,
    RegressionReport,
    SliceReport,
    TrendDirection,
    TrendPoint,
    TrendReport,
)
from .ports import (
    ExperimentComparator,
    FailureClassifier,
    RegressionDetector,
    ResultSlicer,
    TrendAnalyzer,
)
from .regression import WelchRegressionDetector
from .slicing import DimensionSlicer
from .statistics import (
    betai,
    confidence_interval,
    effect_size,
    student_t_cdf,
    student_t_ppf,
    t_test,
)
from .trends import LinearTrendAnalyzer

__all__ = [
    "CategoryFailureClassifier",
    "ComparisonReport",
    "DimensionSlicer",
    "ExperimentComparator",
    "FailureCategory",
    "FailureClassifier",
    "FailureClusterReport",
    "LinearTrendAnalyzer",
    "MetricComparison",
    "RegressionDetector",
    "RegressionReport",
    "ResultSlicer",
    "SliceReport",
    "TrendAnalyzer",
    "TrendDirection",
    "TrendPoint",
    "TrendReport",
    "WelchExperimentComparator",
    "WelchRegressionDetector",
    "betai",
    "confidence_interval",
    "effect_size",
    "student_t_cdf",
    "student_t_ppf",
    "t_test",
]
