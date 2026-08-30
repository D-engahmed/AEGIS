"""Domain exception hierarchy."""

from __future__ import annotations


class AegisError(Exception):
    """Base class for all AEGIS module errors."""


class AegisDomainError(AegisError):
    """Base class for domain rule violations."""


class ValidationFailed(AegisDomainError):
    """One or more domain invariants were violated."""


class NotFound(AegisDomainError):
    """The requested entity does not exist."""


class Conflict(AegisDomainError):
    """A state transition conflicts with an existing resource."""


class InvalidState(AegisDomainError):
    """A state transition is not allowed from the current state."""


class ImmutableResourceViolation(InvalidState):
    """An attempt was made to mutate a locked or immutable resource."""


class InsufficientPermission(AegisDomainError):
    """The actor does not hold the required role for this operation."""
