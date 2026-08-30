"""Datasets (entity group E3): versioned test sets with a draft/locked lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from .events import DomainEvent
from .exceptions import ImmutableResourceViolation, NotFound, ValidationFailed
from .identifiers import VersionLabel, new_id
from .time import Clock


class DatasetStatus(StrEnum):
    DRAFT = "draft"
    LOCKED = "locked"


@dataclass(frozen=True)
class TestCase:
    id: str
    dataset_version_id: str
    index: int
    input: Any
    expected: Any | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Dataset:
    id: str
    organization_id: str
    project_id: str
    name: str
    created_at: datetime


@dataclass(frozen=True)
class DatasetVersion:
    """A test set version. Draft versions are mutable; locked versions are not."""

    id: str
    dataset_id: str
    organization_id: str
    project_id: str
    label: VersionLabel
    status: DatasetStatus = DatasetStatus.DRAFT
    locked_at: datetime | None = None
    test_cases: tuple[TestCase, ...] = field(default_factory=tuple)

    @property
    def test_case_count(self) -> int:
        return len(self.test_cases)

    def _assert_mutable(self) -> None:
        if self.status is not DatasetStatus.DRAFT:
            raise ImmutableResourceViolation(
                f"dataset version {self.id!r} is {self.status.value} and cannot be modified"
            )

    def add_test_case(
        self,
        clock: Clock,
        input: Any,
        expected: Any | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DatasetVersion:
        """Append a test case to a draft version."""
        self._assert_mutable()
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, Mapping):
            raise ValidationFailed("test case metadata must be a mapping")
        test_case = TestCase(
            id=new_id("tc"),
            dataset_version_id=self.id,
            index=self.test_case_count,
            input=input,
            expected=expected,
            metadata=dict(metadata),
        )
        return replace(self, test_cases=self.test_cases + (test_case,))

    def remove_test_case(self, test_case_id: str) -> DatasetVersion:
        """Remove a test case from a draft version."""
        self._assert_mutable()
        remaining = tuple(tc for tc in self.test_cases if tc.id != test_case_id)
        if len(remaining) == self.test_case_count:
            raise NotFound(f"test case {test_case_id!r} not found in dataset version {self.id!r}")
        return replace(self, test_cases=remaining)

    def lock(self, clock: Clock) -> DatasetVersion:
        """Lock a non-empty draft version: immutable from this point on."""
        self._assert_mutable()
        if self.test_case_count == 0:
            raise ValidationFailed(
                f"dataset version {self.id!r} cannot be locked with zero test cases"
            )
        return replace(self, status=DatasetStatus.LOCKED, locked_at=clock.now())


def create_dataset(
    clock: Clock,
    organization_id: str,
    project_id: str,
    name: str,
) -> Dataset:
    if not name or not name.strip():
        raise ValidationFailed("dataset name must not be empty")
    return Dataset(
        id=new_id("ds"),
        organization_id=organization_id,
        project_id=project_id,
        name=name.strip(),
        created_at=clock.now(),
    )


def create_dataset_version(
    clock: Clock,
    dataset: Dataset,
    label: str | VersionLabel,
) -> tuple[DatasetVersion, DomainEvent]:
    """Open a new draft version of a dataset."""
    parsed = label if isinstance(label, VersionLabel) else VersionLabel(label)
    version = DatasetVersion(
        id=new_id("dsv"),
        dataset_id=dataset.id,
        organization_id=dataset.organization_id,
        project_id=dataset.project_id,
        label=parsed,
    )
    from .events import emit

    event = emit(
        clock,
        "dataset_version.created",
        "DatasetVersion",
        version.id,
        dataset_id=dataset.id,
        label=str(parsed),
    )
    return version, event


def add_test_case(
    clock: Clock,
    version: DatasetVersion,
    input: Any,
    expected: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[DatasetVersion, DomainEvent]:
    """Add a test case to a draft version and record the fact."""
    updated = version.add_test_case(clock, input=input, expected=expected, metadata=metadata)
    from .events import emit

    event = emit(
        clock,
        "test_case.added",
        "DatasetVersion",
        updated.id,
        dataset_id=updated.dataset_id,
        test_case_count=updated.test_case_count,
    )
    return updated, event


def remove_test_case(
    clock: Clock,
    version: DatasetVersion,
    test_case_id: str,
) -> tuple[DatasetVersion, DomainEvent]:
    """Remove a test case from a draft version and record the fact."""
    updated = version.remove_test_case(test_case_id)
    from .events import emit

    event = emit(
        clock,
        "test_case.removed",
        "DatasetVersion",
        updated.id,
        dataset_id=updated.dataset_id,
        test_case_count=updated.test_case_count,
    )
    return updated, event


def lock_dataset_version(
    clock: Clock,
    version: DatasetVersion,
) -> tuple[DatasetVersion, DomainEvent]:
    """Lock a draft version; subsequent updates are rejected."""
    locked = version.lock(clock)
    from .events import dataset_version_locked

    event = dataset_version_locked(clock, locked.id, locked.dataset_id, locked_by="system")
    return locked, event


__all__ = [
    "Dataset",
    "DatasetStatus",
    "DatasetVersion",
    "TestCase",
    "add_test_case",
    "create_dataset",
    "create_dataset_version",
    "lock_dataset_version",
    "remove_test_case",
]
