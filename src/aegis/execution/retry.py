"""Bounded retry policy with exponential backoff and jitter.

Never retries indefinitely: should_retry() returns False past max_attempts or
for any non-transient failure class (failure-architecture.md).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from aegis.domain import FailureClass


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


__all__ = ["RetryPolicy"]
