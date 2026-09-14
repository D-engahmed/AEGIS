"""Security mappers: tokens, PII redaction, and audit entries to wire shapes.

Tokens and PII redaction have wire schemas; audit entries are intentionally
untyped wire dicts (see routers/security.py) — centralized here so the
shape lives in one place.
"""

from __future__ import annotations

from ..schemas import PiiRedactOut, TokenOut


def token_out(token: str, context) -> TokenOut:
    return TokenOut(
        token=token,
        expires_at=context.token_expiry or context.authenticated_at,
        authentication_method=context.authentication_method.value,
    )


def pii_redact_out(redacted: str, matches) -> PiiRedactOut:
    return PiiRedactOut(
        redacted=redacted,
        pii_spans=[
            {
                "pii_type": m.pii_type.value,
                "start": m.start,
                "end": m.end,
                "redacted_value": m.redacted_value,
            }
            for m in matches
        ],
    )


def audit_entry_out(entry) -> dict[str, object]:
    return {
        "event_id": entry.event_id,
        "timestamp": entry.timestamp,
        "actor_id": entry.actor_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "organization_id": entry.organization_id,
        "result": entry.result,
        "metadata": entry.metadata,
    }


__all__ = ["audit_entry_out", "pii_redact_out", "token_out"]
