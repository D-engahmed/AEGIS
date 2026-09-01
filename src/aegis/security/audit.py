"""Append-only audit trail and secret storage.

The audit logger is append-only by design: entries are immutable, and the
in-memory implementation never mutates an entry after it is recorded. The
secrets provider is a dev/test stand-in; production swaps in Vault or a cloud
KMS behind the same protocol.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from aegis.domain import ValidationFailed
from aegis.domain.identifiers import new_id

from .models import AuditEntry
from .pii import RegexPIIDetector
from .ports import AuditLogger, SecretsProvider


class MemoryAuditLogger(AuditLogger):
    """Thread-safe, append-only in-memory audit trail."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._detector = RegexPIIDetector()

    def log(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def record(self, **fields: Any) -> AuditEntry:
        """Build and record an entry, redacting any PII present in metadata."""
        metadata = self._redact(dict(fields.get("metadata") or {}))
        entry = AuditEntry(
            event_id=new_id("aud"),
            timestamp=fields.get("timestamp") or datetime.now(),
            actor_id=str(fields["actor_id"]),
            action=str(fields["action"]),
            resource_type=str(fields.get("resource_type", "")),
            resource_id=str(fields.get("resource_id", "")),
            organization_id=str(fields.get("organization_id", "")),
            result=str(fields.get("result", "SUCCESS")),
            metadata=metadata,
        )
        self._entries.append(entry)
        return entry

    def query(
        self,
        organization_id: str,
        actor_id: str | None = None,
        resource_type: str | None = None,
        since: datetime | None = None,
    ) -> list[AuditEntry]:
        result = [
            entry
            for entry in self._entries
            if entry.organization_id == organization_id
            and (actor_id is None or entry.actor_id == actor_id)
            and (resource_type is None or entry.resource_type == resource_type)
            and (since is None or entry.timestamp >= since)
        ]
        return result

    def _redact(self, metadata: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, str) and self._detector.detect(value):
                redacted[key] = self._detector.redact(value)
            else:
                redacted[key] = value
        return redacted


class InMemorySecretsProvider(SecretsProvider):
    """Dev/test secret store; generational rotation keeps old values map-bound."""

    def __init__(self) -> None:
        self._generations: dict[str, str] = {}

    def get_secret(self, secret_id: str) -> str:
        if secret_id not in self._generations:
            raise ValidationFailed(f"secret {secret_id!r} is not provisioned")
        return self._generations[secret_id]

    def set_secret(self, secret_id: str) -> str:
        value = secrets.token_hex(32)
        self._generations[secret_id] = value
        return value

    def rotate_secret(self, secret_id: str) -> None:
        self.set_secret(secret_id)


__all__ = ["InMemorySecretsProvider", "MemoryAuditLogger"]
