"""Cooperative cancellation tokens — re-exported from domain layer.

The canonical definition moved to ``domain.cancellation`` to fix the
infrastructure → execution wrong-direction import.  This module re-exports
for backward compatibility.
"""

from aegis.domain.cancellation import CancellationRequested, CancellationToken

__all__ = ["CancellationToken", "CancellationRequested"]
