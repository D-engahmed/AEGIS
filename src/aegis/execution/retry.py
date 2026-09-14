"""Bounded retry policy — re-exported from domain layer.

The canonical definition moved to ``domain.policies`` to keep value objects
in the domain layer.  This module re-exports for backward compatibility.
"""

from aegis.domain.policies import RetryPolicy

__all__ = ["RetryPolicy"]
