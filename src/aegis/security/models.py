"""Security foundations: identity, permissions, classification, audit.

These are cross-cutting value objects consumed by every higher layer (the
interface for auth middleware, the evidence layer for PII redaction, the
observability layer for telemetry filtering). Immutable by design so identity
and audit decisions can never be rewritten after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aegis.domain.tenants import Role


class AuthMethod(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"


class Permission(StrEnum):
    EXPERIMENT_CREATE = "experiment.create"
    EXPERIMENT_VIEW = "experiment.view"
    EXPERIMENT_START = "experiment.start"
    EXPERIMENT_CANCEL = "experiment.cancel"
    RUN_VIEW = "run.view"
    RUN_CANCEL = "run.cancel"
    RESULT_VIEW = "result.view"
    POLICY_MODIFY = "policy.modify"
    POLICY_OVERRIDE = "policy.override"
    DATASET_MANAGE = "dataset.manage"
    TARGET_MANAGE = "target.manage"
    ORGANIZATION_MANAGE = "organization.manage"
    PROJECT_MANAGE = "project.manage"


class PIIType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    REGULATED = "regulated"


@dataclass(frozen=True)
class Credentials:
    """One credential field is populated for each authentication method."""

    bearer_token: str | None = None
    api_key: str | None = None
    service_account_token: str | None = None

    def __post_init__(self) -> None:
        methods = sum(
            value is not None
            for value in (self.bearer_token, self.api_key, self.service_account_token)
        )
        if methods != 1:
            from aegis.domain import ValidationFailed

            raise ValidationFailed("credentials require exactly one authentication method")


@dataclass(frozen=True)
class AuthContext:
    """The verified identity attached to every request and background job."""

    user_id: str
    organization_id: str
    project_id: str | None
    role: Role
    authentication_method: AuthMethod
    authenticated_at: datetime
    token_expiry: datetime | None = None

    @property
    def can_override_gates(self) -> bool:
        """Only owners/admins override safety gates (deployment-strategy.md)."""
        return (
            self.role.can_override_gates
            and self.authentication_method is not AuthMethod.SERVICE_ACCOUNT
        )


@dataclass(frozen=True)
class PIIMatch:
    pii_type: PIIType
    start: int
    end: int
    redacted_value: str


@dataclass(frozen=True)
class AuditEntry:
    """Immutable, append-only record of a security-relevant action."""

    event_id: str
    timestamp: datetime
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    organization_id: str
    result: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RedactedString:
    """String that masks its content in __repr__/__str__ to avoid log leaks."""

    _value: str

    def reveal(self) -> str:
        """The raw value; use only when writing to a trusted sink."""
        return self._value

    def __str__(self) -> str:
        return "********"

    def __repr__(self) -> str:
        return "RedactedString(********)"


__all__ = [
    "AuditEntry",
    "AuthContext",
    "AuthMethod",
    "Credentials",
    "DataClassification",
    "PIIMatch",
    "PIIType",
    "Permission",
    "RedactedString",
]
