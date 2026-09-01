"""Bounded retry policy and mandatory timeouts."""

from datetime import timedelta

import pytest

from aegis.domain import FailureCode
from aegis.domain.failures import classify_failure
from aegis.execution.retry import RetryPolicy
from aegis.execution.timeout import TimeoutPolicy

pytestmark = pytest.mark.unit


def test_only_transient_failures_are_retried() -> None:
    policy = RetryPolicy(max_attempts=3)
    transient = classify_failure(FailureCode.TEMPORARY_UNAVAILABLE)
    assert transient.retryable
    assert policy.should_retry(transient, 0)
    assert policy.should_retry(transient, 1)
    assert not policy.should_retry(transient, 2)
    for code in (
        FailureCode.SCHEMA_MISMATCH,
        FailureCode.MALFORMED_RESPONSE,
        FailureCode.SECRET_INCIDENT,
    ):
        cls = classify_failure(code)
        assert not cls.retryable
        assert not policy.should_retry(cls, 0)
        assert not policy.should_retry(cls, 99)


def test_no_infinite_retry_path() -> None:
    policy = RetryPolicy(max_attempts=1)
    transient = classify_failure(FailureCode.PROVIDER_RATE_LIMIT)
    assert not policy.should_retry(transient, 0)
    assert not policy.should_retry(transient, 1)
    assert not policy.should_retry(transient, 2**10)


def test_invalid_policies_are_rejected() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay_seconds=-1)
    with pytest.raises(ValueError):
        RetryPolicy(jitter_ratio=-0.1)
    with pytest.raises(ValueError):
        RetryPolicy(max_delay_seconds=0.5, base_delay_seconds=1.0)


def test_backoff_without_jitter_is_deterministic() -> None:
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=100.0, jitter_ratio=0.0)
    assert policy.delay_for(0) == 1.0
    assert policy.delay_for(1) == 2.0
    assert policy.delay_for(2) == 4.0
    assert policy.delay_for(10) == 100.0


def test_jitter_keeps_delay_within_bounds() -> None:
    policy = RetryPolicy(base_delay_seconds=10.0, max_delay_seconds=30.0, jitter_ratio=0.2)
    for attempt in range(5):
        delay = policy.delay_for(attempt, lambda: 1.0)
        assert 10.0 <= delay <= 30.0
    assert policy.delay_for(3, lambda: 1.0) == 30.0


def test_timeout_deadlines_and_expiry() -> None:
    policy = TimeoutPolicy(per_test_seconds=5, per_target_seconds=10, per_experiment_seconds=15)
    from datetime import UTC, datetime

    start = datetime(2026, 8, 30, tzinfo=UTC)
    assert not policy.expired(start, start + timedelta(seconds=4), policy.per_test_seconds)
    assert policy.expired(start, start + timedelta(seconds=6), policy.per_test_seconds)
    assert not policy.expired(start, start + timedelta(seconds=9), policy.per_target_seconds)
    assert policy.expired(start, start + timedelta(seconds=16), policy.per_experiment_seconds)


def test_invalid_timeouts_are_rejected() -> None:
    with pytest.raises(ValueError):
        TimeoutPolicy(per_test_seconds=0)
    with pytest.raises(ValueError):
        TimeoutPolicy(per_test_seconds=-1)
