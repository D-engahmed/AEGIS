"""Time source abstraction so the domain layer stays pure and testable."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Source of wall-clock time, injected as the single source of time."""

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        ...


class SystemClock:
    """Clock backed by the system wall clock (UTC)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Clock pinned to a fixed instant for reproducible tests."""

    def __init__(self, at: datetime | None = None) -> None:
        self._at = at or datetime(2026, 8, 30, tzinfo=UTC)

    def now(self) -> datetime:
        return self._at


__all__ = ["Clock", "FrozenClock", "SystemClock", "UTC"]
