"""Pure-Python statistics used by analysis (no scipy/numpy dependency).

Implements Welch's t-test with two-sided p-value via the regularized incomplete
beta function (Numerical Recipes betacf), a confidence interval from the t
quantile (bisection over the CDF), and Cohen's d effect size. Sample-size
guards are applied at the analysis call sites, not here.
"""

from __future__ import annotations

import math
from statistics import mean, stdev

_EPS = 3.0e-12
_FPMIN = 1.0e-300
_MAX_IT = 200


def _betacf(a: float, b: float, x: float) -> float:
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _MAX_IT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: float) -> float:
    """Cumulative distribution of Student's t at `t`."""
    x = df / (df + t * t)
    if t >= 0:
        return 1.0 - 0.5 * betai(df / 2.0, 0.5, x)
    return 0.5 * betai(df / 2.0, 0.5, x)


def student_t_ppf(p: float, df: float) -> float:
    """Quantile of Student's t via bisection over the CDF."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0, 1), got {p!r}")
    lower, upper = -16.0, 16.0
    for _ in range(200):
        mid = 0.5 * (lower + upper)
        if student_t_cdf(mid, df) < p:
            lower = mid
        else:
            upper = mid
    return 0.5 * (lower + upper)


def t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch's t-test: returns (t_statistic, two_sided_p_value)."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Welch's t-test requires at least two samples per group")
    n_a, n_b = len(a), len(b)
    mean_a, mean_b = mean(a), mean(b)
    var_a = stdev(a) ** 2
    var_b = stdev(b) ** 2
    denominator = math.sqrt(var_a / n_a + var_b / n_b)
    t_stat = 0.0 if denominator == 0.0 else (mean_a - mean_b) / denominator
    df = _welch_df(var_a / n_a, var_b / n_b, n_a, n_b)
    return t_stat, 1.0 - student_t_cdf(t_stat, df)


def _welch_df(sa: float, sb: float, n_a: int, n_b: int) -> float:
    numerator = (sa + sb) ** 2
    denominator = (sa**2) / (n_a - 1) + (sb**2) / (n_b - 1)
    if denominator == 0.0:
        return float(n_a + n_b - 2)
    return numerator / denominator


def confidence_interval(data: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """Confidence interval for the mean using the t quantile."""
    if len(data) < 2:
        raise ValueError("confidence interval requires at least two samples")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence!r}")
    sample_mean = mean(data)
    standard_error = stdev(data) / math.sqrt(len(data))
    margin = student_t_ppf(0.5 + confidence / 2.0, len(data) - 1) * standard_error
    return sample_mean - margin, sample_mean + margin


def effect_size(a: list[float], b: list[float]) -> float:
    """Cohen's d with pooled standard deviation."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError("effect size requires at least two samples per group")
    n_a, n_b = len(a), len(b)
    pooled_variance = ((n_a - 1) * (stdev(a) ** 2) + (n_b - 1) * (stdev(b) ** 2)) / (n_a + n_b - 2)
    pooled_stdev = math.sqrt(pooled_variance)
    if pooled_stdev == 0.0:
        return 0.0
    return (mean(a) - mean(b)) / pooled_stdev


__all__ = [
    "betai",
    "confidence_interval",
    "effect_size",
    "student_t_cdf",
    "student_t_ppf",
    "t_test",
]
