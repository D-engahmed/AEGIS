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
from .execution import (
    EvidenceSummary,
    ExecutionOutcome,
    ExecutionRecord,
    ExecutionStatus,
    FailureInfo,
    Run,
    RunStatus,
    TokenUsage,
)
from .experiments import Experiment, ExperimentSnapshot, ExperimentStatus
from .failures import FailureClass, FailureCode, classify_failure, is_retryable
from .registry import RegistryReference
from .results import EvidenceReference, EvidenceViolation, MetricResult, new_metric_result
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
    "EvidenceReference",
    "EvidenceSummary",
    "EvidenceViolation",
    "ExecutionOutcome",
    "ExecutionRecord",
    "ExecutionStatus",
    "Experiment",
    "ExperimentSnapshot",
    "ExperimentStatus",
    "FailureClass",
    "FailureCode",
    "FailureInfo",
    "FrozenClock",
    "ImmutableResourceViolation",
    "InsufficientPermission",
    "InvalidState",
    "Membership",
    "MetricResult",
    "NotFound",
    "Organization",
    "Project",
    "RegistryReference",
    "Role",
    "Run",
    "RunStatus",
    "SystemClock",
    "Target",
    "TargetType",
    "TargetVersion",
    "TestCase",
    "TokenUsage",
    "UTC",
    "ValidationFailed",
    "classify_failure",
    "is_retryable",
    "new_metric_result",
]
