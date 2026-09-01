"""FastAPI dependencies: container access, auth, tenant, and permissions.

Every protected route resolves the caller's AuthContext from the signed bearer
token, builds the tenancy root from the verified identity (the token IS the
source of truth for membership in the in-memory profile), and then enforces
the RBAC permission before the handler runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from aegis.domain import Organization
from aegis.domain.tenants import Membership
from aegis.domain.time import UTC
from aegis.security.models import AuthContext, Permission

from .container import Container

_BEARER = "Bearer "


@dataclass(frozen=True)
class Actor:
    """Verified caller plus the tenancy root they act within."""

    context: AuthContext
    organization: Organization


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_actor(
    container: Annotated[Container, Depends(get_container)],
    authorization: Annotated[str | None, Header()] = None,
) -> Actor:
    """Authenticate the bearer token and build the tenant root."""
    if not authorization or not authorization.startswith(_BEARER):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len(_BEARER) :]
    context = container.auth.validate_token(token, now=container.clock.now())
    membership = Membership(context.organization_id, context.user_id, context.role)
    organization = Organization(
        id=context.organization_id,
        name=f"org-{context.organization_id}",
        created_at=context.authenticated_at,
        members=(membership,),
    )
    return Actor(context=context, organization=organization)


require_actor = Annotated[Actor, Depends(get_actor)]


def require_permission(permission: Permission) -> Callable:
    """Dependency factory: returns a dependency that enforces one RBAC permission."""

    def dependency(
        actor: require_actor,
        container: Annotated[Container, Depends(get_container)],
    ) -> Actor:
        org_id = actor.context.organization_id
        container.rbac.check(actor.context, permission, org_id)
        return actor

    return dependency


def audit(
    container: Annotated[Container, Depends(get_container)],
    actor: require_actor,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    result: str = "SUCCESS",
) -> None:
    """Record a security-relevant action on the append-only audit trail."""
    container.audit.record(
        actor_id=actor.context.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id or "",
        organization_id=actor.context.organization_id,
        result=result,
        timestamp=container.clock.now(),
    )


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "Actor",
    "audit",
    "get_actor",
    "get_container",
    "now_iso",
    "require_actor",
    "require_permission",
]
