"""Cooperative cancellation tokens (cancellation flow, async-execution-contract.md).

Cancellation is never mid-flight: the engine checks the token between test
cases and between retry sleeps, then transitions to a distinguishable CANCELLED
state with partial evidence preserved.
"""

from __future__ import annotations

from datetime import datetime


class CancellationRequested(Exception):
    """Raised when an active run should stop cooperating."""

    def __init__(self, run_id: str, identity: str) -> None:
        super().__init__(f"run {run_id!r} cancelled by {identity}")
        self.run_id = run_id
        self.identity = identity


class CancellationToken:
    """Immutable snapshot of a cancel request for one run."""

    def __init__(self, run_id: str, identity: str, at: datetime) -> None:
        self.run_id = run_id
        self.identity = identity
        self.at = at

    @property
    def is_cancelled(self) -> bool:
        return True

    def raise_if_cancelled(self) -> None:
        raise CancellationRequested(self.run_id, self.identity)


__all__ = ["CancellationToken", "CancellationRequested"]
