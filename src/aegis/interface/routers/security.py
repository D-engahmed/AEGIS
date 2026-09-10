"""Security endpoints: token issuance, PII redaction, and audit trail."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from aegis.domain.tenants import Role
from aegis.domain.time import UTC
from aegis.security.models import AuthMethod, Permission

from ..container import Container
from ..deps import Actor, get_container, require_permission
from ..schemas import PiiRedactIn, PiiRedactOut, TokenOut

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/dev-token", response_model=TokenOut, include_in_schema=False)
def dev_token(
    container: Annotated[Container, Depends(get_container)],
    user_id: str = "user:dev",
    organization_id: str = "org:1",
    project_id: str | None = None,
    role: str = "admin",
) -> TokenOut:
    """Mint a token from an explicit identity (development login only).

    Disabled unless AEGIS_DEV_LOGIN=1; never enable on prod deployments.
    """
    if os.environ.get("AEGIS_DEV_LOGIN") != "1":
        raise HTTPException(status_code=403, detail="dev login disabled")
    token = container.auth.issue(
        user_id=user_id,
        organization_id=organization_id,
        role=Role(role),
        project_id=project_id,
        method=AuthMethod.SERVICE_ACCOUNT,
        now=container.clock.now(),
    )
    context = container.auth.validate_token(token, now=container.clock.now())
    return TokenOut(
        token=token,
        expires_at=context.token_expiry or context.authenticated_at,
        authentication_method=context.authentication_method.value,
    )


@router.post("/tokens", response_model=TokenOut, status_code=201)
def issue_token(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> TokenOut:
    """Issue a fresh signed token for the authenticated caller.

    Used to mint short-lived tokens for worker processes; the caller must
    already hold a valid token (the token itself is the identity source).
    """
    token = container.auth.issue(
        user_id=actor.context.user_id,
        organization_id=actor.context.organization_id,
        role=Role(actor.context.role.value),
        project_id=actor.context.project_id,
        method=AuthMethod.SERVICE_ACCOUNT,
        now=container.clock.now(),
    )
    context = container.auth.validate_token(token, now=container.clock.now())
    return TokenOut(
        token=token,
        expires_at=context.token_expiry or context.authenticated_at,
        authentication_method=context.authentication_method.value,
    )


@router.post("/pii/redact", response_model=PiiRedactOut)
def redact_pii(
    payload: PiiRedactIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> PiiRedactOut:
    """Redact PII spans from free text; returns the masked text and match list."""
    actor.organization.require_membership(actor.context.user_id)
    matches = container.pii.detect(payload.text)
    return PiiRedactOut(
        redacted=container.pii.redact(payload.text),
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


@router.get("/audit")
def list_audit(
    actor: Annotated[Actor, Depends(require_permission(Permission.RUN_VIEW))],
    container: Annotated[Container, Depends(get_container)],
    actor_id: str | None = None,
    resource_type: str | None = None,
) -> list[dict[str, object]]:
    """Return the append-only audit trail for the caller's tenant."""
    actor.organization.require_membership(actor.context.user_id)
    entries = container.audit.query(
        actor.context.organization_id,
        actor_id=actor_id,
        resource_type=resource_type,
    )
    return [
        {
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "actor_id": e.actor_id,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "organization_id": e.organization_id,
            "result": e.result,
            "metadata": e.metadata,
        }
        for e in entries
    ]


@router.get("/now", include_in_schema=False)
def server_time() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["router"]
