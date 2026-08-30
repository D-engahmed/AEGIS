"""Domain events: immutable facts emitted by domain operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .identifiers import new_id
from .time import Clock


@dataclass(frozen=True)
class DomainEvent:
    """An immutable record of something that happened in the domain.

    The payload is intentionally shallow (dict of primitives) so events remain
    serializable across process boundaries.
    """

    event_id: str
    name: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


def emit(
    clock: Clock,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    **payload: Any,
) -> DomainEvent:
    """Build a fully populated, immutable domain event."""
    return DomainEvent(
        event_id=new_id("evt"),
        name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        occurred_at=clock.now(),
        payload=payload,
    )


def organization_created(
    clock: Clock, organization_id: str, name: str, created_by: str
) -> DomainEvent:
    return emit(
        clock,
        "organization.created",
        "Organization",
        organization_id,
        name=name,
        created_by=created_by,
    )


def project_created(
    clock: Clock,
    project_id: str,
    organization_id: str,
    name: str,
    created_by: str,
) -> DomainEvent:
    return emit(
        clock,
        "project.created",
        "Project",
        project_id,
        organization_id=organization_id,
        name=name,
        created_by=created_by,
    )


def dataset_version_locked(
    clock: Clock,
    dataset_version_id: str,
    dataset_id: str,
    locked_by: str,
) -> DomainEvent:
    return emit(
        clock,
        "dataset_version.locked",
        "DatasetVersion",
        dataset_version_id,
        dataset_id=dataset_id,
        locked_by=locked_by,
    )


def target_version_referenced(
    clock: Clock,
    target_version_id: str,
    target_id: str,
    dataset_version_id: str,
) -> DomainEvent:
    return emit(
        clock,
        "target_version.referenced",
        "TargetVersion",
        target_version_id,
        target_id=target_id,
        dataset_version_id=dataset_version_id,
    )


__all__ = [
    "DomainEvent",
    "dataset_version_locked",
    "emit",
    "organization_created",
    "project_created",
    "target_version_referenced",
]
