"""Registry (entity group E4): evidence-backed references between domain roots.

A RegistryReference pins the target versions that will be evaluated against a
database source (the immutability rule "no score without evidence" is enforced
later in the evaluation/evidence layers). Registering a target version flags it
as referenced, freezing its configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .events import DomainEvent
from .exceptions import NotFound, ValidationFailed
from .identifiers import new_id
from .targets import TargetVersion
from .time import Clock


@dataclass(frozen=True)
class RegistryReference:
    """Pins a database source (dataset version) to evaluated target versions."""

    id: str
    organization_id: str
    project_id: str
    source_dataset_version_id: str
    registered_by: str
    created_at: datetime
    target_version_ids: tuple[str, ...] = ()

    def add_reference(
        self,
        target_version: TargetVersion,
    ) -> RegistryReference:
        if target_version.id in self.target_version_ids:
            return self
        return replace(
            self,
            target_version_ids=self.target_version_ids + (target_version.id,),
        )


def register_source(
    clock: Clock,
    organization_id: str,
    project_id: str,
    dataset_version_id: str,
    registered_by: str,
) -> RegistryReference:
    """Open a registration slot for a dataset version."""
    if not dataset_version_id:
        raise ValidationFailed("dataset version id must not be empty")
    return RegistryReference(
        id=new_id("ref"),
        organization_id=organization_id,
        project_id=project_id,
        source_dataset_version_id=dataset_version_id,
        registered_by=registered_by,
        created_at=clock.now(),
    )


def annex_target(
    clock: Clock,
    reference: RegistryReference,
    target_version: TargetVersion,
) -> tuple[RegistryReference, TargetVersion, DomainEvent]:
    """Annex a target version to the source; the version becomes referenced."""
    from .events import target_version_referenced

    updated_reference = reference.add_reference(target_version)
    referenced = target_version.mark_referenced()
    event = target_version_referenced(
        clock,
        referenced.id,
        referenced.target_id,
        reference.source_dataset_version_id,
    )
    return updated_reference, referenced, event


def require_registered(reference: RegistryReference, dataset_version_id: str) -> None:
    """Guard: a source must be registered before it can be evaluated."""
    if reference.source_dataset_version_id != dataset_version_id:
        raise NotFound(f"no registration found for dataset version {dataset_version_id!r}")


__all__ = [
    "RegistryReference",
    "annex_target",
    "register_source",
    "require_registered",
]
