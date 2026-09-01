"""Policy ports: storage for persisted run gate verdicts and overrides.

Concrete implementations live in the infrastructure layer; policy and interface
consumers depend only on these protocols.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import RunGateReport


@runtime_checkable
class RunGateStore(Protocol):
    """Write-once-ish storage of the run's gate report (override replaces it)."""

    def save(self, report: RunGateReport) -> None: ...

    def load(self, run_id: str) -> RunGateReport: ...

    def exists(self, run_id: str) -> bool: ...


__all__ = ["RunGateStore"]
