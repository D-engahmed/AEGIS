"""Catalog application service: register targets and datasets (layer 02).

Owns the orchestration of creating a target or dataset and its first version,
so both the HTTP router and the CLI share one implementation. The interface
layer handles HTTP concerns (auth, DTO mapping, audit) or CLI concerns
(file loading, argument defaults); this service owns the domain workflow.
"""

from __future__ import annotations

from aegis.domain.datasets import (
    DatasetVersion,
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.targets import TargetType, TargetVersion, create_target, create_target_version
from aegis.domain.time import Clock


class CatalogService:
    """Register targets and datasets through the data catalog port."""

    def __init__(self, clock: Clock, catalog) -> None:
        self._clock = clock
        self._catalog = catalog

    def register_target(
        self,
        organization_id: str,
        project_id: str,
        name: str,
        target_type: TargetType,
        label: str,
        config: dict,
        *,
        commit_sha: str | None = None,
    ) -> TargetVersion:
        """Create a target and its first immutable version, then register both."""
        target = create_target(self._clock, organization_id, project_id, name, target_type)
        version = create_target_version(self._clock, target, label, config, commit_sha=commit_sha)
        self._catalog.register_target_record(target)
        self._catalog.register_target(version)
        return version

    def register_dataset(
        self,
        organization_id: str,
        project_id: str,
        name: str,
        label: str,
        test_cases: list[dict],
    ) -> DatasetVersion:
        """Create a dataset with a draft version and its initial test cases."""
        dataset = create_dataset(self._clock, organization_id, project_id, name)
        version, _event = create_dataset_version(self._clock, dataset, label)
        for tc in test_cases:
            version, _event = add_test_case(
                self._clock,
                version,
                input=tc["input"],
                expected=tc["expected"],
                metadata=tc.get("metadata", {}),
            )
        self._catalog.register_dataset_record(dataset)
        self._catalog.register_dataset(version)
        return version

    def register_dataset_locked(
        self,
        organization_id: str,
        project_id: str,
        name: str,
        label: str,
        test_cases: list[dict],
    ) -> DatasetVersion:
        """Create a dataset, populate test cases, and lock immediately (CLI)."""
        dataset = create_dataset(self._clock, organization_id, project_id, name)
        version, _event = create_dataset_version(self._clock, dataset, label)
        for tc in test_cases:
            version, _event = add_test_case(
                self._clock,
                version,
                input=tc["input"],
                expected=tc["expected"],
                metadata=tc.get("metadata", {}),
            )
        locked, _event = lock_dataset_version(self._clock, version)
        self._catalog.register_dataset_record(dataset)
        self._catalog.register_dataset(locked)
        return locked


__all__ = ["CatalogService"]
