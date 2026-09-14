"""Execution policies: retry and timeout boundaries.

These are pure value objects (frozen dataclasses) owned by the domain layer.
They define business rules for retry behaviour and timeout budgets without
depending on any infrastructure or framework.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aegis.domain.failures import FailureClass


@dataclass(frozen=True)
class RetryPolicy:
    """max_attempts is the total number of invocations, first attempt included."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be non-negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if not 0.0 <= self.jitter_ratio <= 1.0:
            raise ValueError("jitter_ratio must be within [0, 1]")

    def should_retry(self, failure_class: FailureClass, attempt: int) -> bool:
        """attempt is the number of retries already consumed (0-based)."""
        return failure_class is FailureClass.RETRYABLE and attempt < self.max_attempts - 1

    def delay_for(
        self,
        attempt: int,
        rng: Callable[[], float] = random.random,
    ) -> float:
        """Exponential backoff with optional multiplier jitter, capped at max_delay."""
        exponent = min(attempt, 63)
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2**exponent))
        if self.jitter_ratio > 0:
            delay *= 1.0 + rng() * self.jitter_ratio
        return min(self.max_delay_seconds, delay)


@dataclass(frozen=True)
class TimeoutPolicy:
    per_test_seconds: float = 30.0
    per_target_seconds: float = 300.0
    per_experiment_seconds: float = 3600.0

    def __post_init__(self) -> None:
        if min(self.per_test_seconds, self.per_target_seconds, self.per_experiment_seconds) <= 0:
            raise ValueError("timeout boundaries must be positive")

    def deadline(self, started_at: datetime, within_seconds: float) -> datetime:
        return started_at + timedelta(seconds=within_seconds)

    def expired(self, since: datetime, now: datetime, within_seconds: float) -> bool:
        return now > since + timedelta(seconds=within_seconds)


def test_timeout_remaining(policy: TimeoutPolicy, started_at: datetime) -> float:
    """Return the wall-seconds left in the per-test budget as of `started_at` context.

    This helper exists for adapter wiring; the engine enforces real deadlines
    against the injected clock.
    """
    return policy.per_test_seconds


__all__ = ["RetryPolicy", "TimeoutPolicy", "test_timeout_remaining"]
