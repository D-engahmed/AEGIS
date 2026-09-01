"""Health checks and aggregation over infrastructure dependencies."""

from __future__ import annotations

from typing import Protocol

from .models import HealthStatus


class HealthCheck(Protocol):
    """A single dependency's health probe."""

    @property
    def name(self) -> str: ...

    def check(self) -> HealthStatus: ...


class HealthAggregator:
    """Composes health checks; unhealthy wins over degraded over healthy."""

    def __init__(self, checks: list[HealthCheck] | None = None) -> None:
        self._checks: list[HealthCheck] = list(checks or [])

    def register(self, check: HealthCheck) -> None:
        self._checks.append(check)

    def aggregate(self) -> dict[str, str]:
        return {check.name: check.check().value for check in self._checks}

    def is_healthy(self) -> bool:
        return all(check.check() is HealthStatus.HEALTHY for check in self._checks)


class StaticHealthCheck:
    """Health check pinned to a fixed status (used for wiring and tests)."""

    def __init__(self, name: str, status: HealthStatus, detail: str | None = None) -> None:
        self._name = name
        self._status = status
        self._detail = detail

    @property
    def name(self) -> str:
        return self._name

    def check(self) -> HealthStatus:
        return self._status


__all__ = ["HealthAggregator", "HealthCheck", "StaticHealthCheck"]
