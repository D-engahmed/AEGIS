"""Unit tests for the tenancy roots (entity group E1)."""

import pytest

from aegis.domain.exceptions import InsufficientPermission, ValidationFailed
from aegis.domain.tenants import (
    Membership,
    Organization,
    Role,
    create_organization,
    create_project,
)
from aegis.domain.time import FrozenClock

pytestmark = pytest.mark.unit


def test_create_organization_makes_creator_owner() -> None:
    clock = FrozenClock()
    org, event = create_organization(clock, "ACME", "u-owner")
    assert org.id.startswith("org:")
    assert org.name == "ACME"
    assert org.membership_of("u-owner") == Membership(org.id, "u-owner", Role.OWNER)
    assert event.name == "organization.created"
    assert event.aggregate_id == org.id


def test_create_organization_rejects_empty_name() -> None:
    with pytest.raises(ValidationFailed):
        create_organization(FrozenClock(), "   ", "u-owner")


def test_add_member_requires_admin_or_owner() -> None:
    clock = FrozenClock()
    org, _ = create_organization(clock, "ACME", "u-owner")
    org = org.add_member("u-owner", "u-eng", Role.ENGINEER)
    assert org.membership_of("u-eng").role is Role.ENGINEER
    with pytest.raises(InsufficientPermission):
        org.add_member("u-eng", "u-analyst", Role.ANALYST)


def test_add_member_rejects_duplicate() -> None:
    clock = FrozenClock()
    org, _ = create_organization(clock, "ACME", "u-owner")
    with pytest.raises(ValidationFailed):
        org.add_member("u-owner", "u-owner", Role.ENGINEER)


def test_require_membership_rejects_outsider() -> None:
    org = Organization(id="org:1", name="ACME", created_at=FrozenClock().now())
    with pytest.raises(InsufficientPermission):
        org.require_membership("u-outsider")


def test_create_project_requires_membership() -> None:
    clock = FrozenClock()
    org, _ = create_organization(clock, "ACME", "u-owner")
    project, event = create_project(org, clock, "core", "u-owner")
    assert project.organization_id == org.id
    assert project.name == "core"
    assert event.name == "project.created"
    with pytest.raises(InsufficientPermission):
        create_project(org, clock, "core", "u-outsider")


def test_role_gate_override_matrix() -> None:
    assert Role.OWNER.can_override_gates
    assert Role.ADMIN.can_override_gates
    assert not Role.ENGINEER.can_override_gates
    assert not Role.ANALYST.can_override_gates
    assert not Role.VIEWER.can_override_gates
