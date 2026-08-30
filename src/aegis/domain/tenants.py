"""Tenancy roots: organizations, memberships and projects (entity group E1)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

from .events import DomainEvent
from .exceptions import InsufficientPermission, ValidationFailed
from .identifiers import new_id
from .time import Clock


class Role(StrEnum):
    """Role-based access: owners/admins may override safety gates."""

    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"

    @property
    def can_override_gates(self) -> bool:
        return self is Role.OWNER or self is Role.ADMIN


@dataclass(frozen=True)
class Membership:
    organization_id: str
    user_id: str
    role: Role


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    created_at: datetime
    members: tuple[Membership, ...] = field(default_factory=tuple)

    def membership_of(self, user_id: str) -> Membership | None:
        for member in self.members:
            if member.user_id == user_id:
                return member
        return None

    def require_membership(self, user_id: str) -> Membership:
        member = self.membership_of(user_id)
        if member is None:
            raise InsufficientPermission(
                f"user {user_id!r} is not a member of organization {self.id!r}"
            )
        return member

    def add_member(self, actor: str, user_id: str, role: Role) -> Organization:
        actor_membership = self.require_membership(actor)
        if actor_membership.role not in (Role.OWNER, Role.ADMIN):
            raise InsufficientPermission(f"user {actor!r} may not manage memberships")
        if self.membership_of(user_id) is not None:
            raise ValidationFailed(f"user {user_id!r} is already a member")
        return replace(self, members=self.members + (Membership(self.id, user_id, role),))


@dataclass(frozen=True)
class Project:
    id: str
    organization_id: str
    name: str
    created_at: datetime


def create_organization(
    clock: Clock,
    name: str,
    created_by: str,
) -> tuple[Organization, DomainEvent]:
    """Create a tenant root. The creator becomes the owner."""
    if not name or not name.strip():
        raise ValidationFailed("organization name must not be empty")
    organization_id = new_id("org")
    organization = Organization(
        id=organization_id,
        name=name.strip(),
        created_at=clock.now(),
        members=(Membership(organization_id, created_by, Role.OWNER),),
    )
    from .events import organization_created

    event = organization_created(clock, organization.id, organization.name, created_by)
    return organization, event


def create_project(
    organization: Organization,
    clock: Clock,
    name: str,
    created_by: str,
) -> tuple[Project, DomainEvent]:
    """Create a project scoped to a tenant; the actor must be a member."""
    organization.require_membership(created_by)
    if not name or not name.strip():
        raise ValidationFailed("project name must not be empty")
    project = Project(
        id=new_id("prj"),
        organization_id=organization.id,
        name=name.strip(),
        created_at=clock.now(),
    )
    from .events import project_created

    event = project_created(clock, project.id, organization.id, project.name, created_by)
    return project, event


__all__ = [
    "Membership",
    "Organization",
    "Project",
    "Role",
    "create_organization",
    "create_project",
]
