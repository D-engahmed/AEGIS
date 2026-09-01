"""Security ports: contracts every consumer depends on (default-deny).

Implementations live alongside (in-memory/HMAC for dev, Vault/KMS in the
infrastructure layer in production). Consumers depend on these protocols, never
on a concrete provider, so the security story can be hardened without touching
the layers that rely on it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .models import AuditEntry, AuthContext, Credentials, DataClassification, Permission, PIIMatch


@runtime_checkable
class AuthProvider(Protocol):
    """Authenticates credentials into a verified identity context."""

    def authenticate(self, credentials: Credentials) -> AuthContext:
        """Verify credentials; raise InsufficientPermission/Unauthorized on failure."""
        ...

    def validate_token(self, token: str) -> AuthContext:
        """Validate a serialized token previously issued by this provider."""
        ...


@runtime_checkable
class PermissionChecker(Protocol):
    """Default-deny role-based authorization."""

    def check(self, context: AuthContext, permission: Permission, resource_org_id: str) -> None:
        """Raise InsufficientPermission unless the actor holds the permission."""
        ...

    def has_permission(
        self, context: AuthContext, permission: Permission, resource_org_id: str
    ) -> bool:
        """True when the actor holds the permission for the given tenant."""
        ...


@runtime_checkable
class TenantScopeGuard(Protocol):
    """Enforces that actors never read or write across tenant boundaries."""

    def require_same_tenant(self, context: AuthContext, resource_org_id: str) -> None:
        """Raise InsufficientPermission when the resource belongs to another tenant."""
        ...


@runtime_checkable
class PIIDetector(Protocol):
    """Finds and redacts personally-identifiable information in text."""

    def detect(self, text: str) -> list[PIIMatch]:
        """Return the PII spans found in the text."""
        ...

    def redact(self, text: str) -> str:
        """Return the text with every PII span masked."""
        ...


@runtime_checkable
class ClassificationAnnotator(Protocol):
    """Assigns a data classification to arbitrary payloads."""

    def classify(self, data: dict[str, Any]) -> DataClassification:
        """Return the most restrictive classification implied by the data."""
        ...


@runtime_checkable
class AuditLogger(Protocol):
    """Append-only security audit trail."""

    def log(self, entry: AuditEntry) -> None:
        """Permanently record a security-relevant action."""
        ...

    def query(
        self,
        organization_id: str,
        actor_id: str | None = None,
        resource_type: str | None = None,
        since: datetime | None = None,
    ) -> list[AuditEntry]:
        """Return matching audit entries, oldest first."""
        ...


@runtime_checkable
class SecretsProvider(Protocol):
    """Secret storage with rotation; used by infrastructure adapters."""

    def get_secret(self, secret_id: str) -> str:
        """Return the current secret value for the id."""
        ...

    def rotate_secret(self, secret_id: str) -> None:
        """Rotate the secret so new reads return a fresh value."""
        ...


__all__ = [
    "AuditLogger",
    "AuthProvider",
    "ClassificationAnnotator",
    "PIIDetector",
    "PermissionChecker",
    "SecretsProvider",
    "TenantScopeGuard",
]
