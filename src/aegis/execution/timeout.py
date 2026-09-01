"""Mandatory timeout policies at three levels (execution-architecture.md).

- per-test:      a single test case invocation is bounded.
- per-target:    total time against a target across test cases is bounded.
- per-experiment: the whole run is bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


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


__all__ = ["TimeoutPolicy"]
