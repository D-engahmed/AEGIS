"""Domain layer (layer 01): pure business entities, rules and events.

Constraints (docs/development/layers/01-domain-layer.md):
- Standard library only - no HTTP/SQL/Redis, no FastAPI/Django/Celery,
  no provider SDKs.
- No I/O and no side effects; clocks are injected so the layer stays pure
  and fully unit-testable.
"""

from .datasets import Dataset, DatasetStatus, DatasetVersion, TestCase
from .events import DomainEvent
from .exceptions import (
    AegisDomainError,
    Conflict,
    ImmutableResourceViolation,
    InsufficientPermission,
    InvalidState,
    NotFound,
    ValidationFailed,
)
from .registry import RegistryReference
from .targets import Target, TargetType, TargetVersion
from .tenants import Membership, Organization, Project, Role
from .time import UTC, Clock, FrozenClock, SystemClock

__all__ = [
    "AegisDomainError",
    "Clock",
    "Conflict",
    "Dataset",
    "DatasetStatus",
    "DatasetVersion",
    "DomainEvent",
    "FrozenClock",
    "ImmutableResourceViolation",
    "InsufficientPermission",
    "InvalidState",
    "Membership",
    "NotFound",
    "Organization",
    "Project",
    "RegistryReference",
    "Role",
    "SystemClock",
    "Target",
    "TargetType",
    "TargetVersion",
    "TestCase",
    "UTC",
    "ValidationFailed",
]
