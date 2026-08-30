"""Unit tests for dataset lifecycle: draft -> lock -> immutable (entity group E3)."""

import pytest

from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
    remove_test_case,
)
from aegis.domain.exceptions import ImmutableResourceViolation, NotFound, ValidationFailed
from aegis.domain.time import FrozenClock

pytestmark = pytest.mark.unit


def _draft(clock: FrozenClock):
    dataset = create_dataset(clock, "org:1", "prj:1", "golden-qa")
    version, _ = create_dataset_version(clock, dataset, "1.0.0")
    return dataset, version


def test_add_and_remove_test_cases() -> None:
    clock = FrozenClock()
    _, version = _draft(clock)
    version, event = add_test_case(
        clock,
        version,
        input={"q": "hi"},
        expected="hello",
        metadata={"lang": "en"},
    )
    assert event.name == "test_case.added"
    assert version.test_case_count == 1
    tc = version.test_cases[0]
    assert tc.index == 0
    assert tc.metadata["lang"] == "en"
    version, _ = add_test_case(clock, version, input="2")
    assert version.test_case_count == 2
    version, _ = remove_test_case(clock, version, tc.id)
    assert version.test_case_count == 1


def test_locked_version_rejects_mutation() -> None:
    clock = FrozenClock()
    _, version = _draft(clock)
    version, _ = add_test_case(clock, version, input="x", expected="y")
    version, _ = lock_dataset_version(clock, version)
    assert version.status.value == "locked"
    assert version.locked_at == clock.now()
    with pytest.raises(ImmutableResourceViolation):
        version.add_test_case(clock, input="x")


def test_lock_requires_at_least_one_test_case() -> None:
    clock = FrozenClock()
    _, version = _draft(clock)
    with pytest.raises(ValidationFailed):
        version.lock(clock)


def test_remove_missing_test_case_raises() -> None:
    clock = FrozenClock()
    _, version = _draft(clock)
    with pytest.raises(NotFound):
        remove_test_case(clock, version, "tc:missing")


def test_abstracted_lifecycle() -> None:
    """Compact end-to-end domain flow: build, populate, lock."""
    clock = FrozenClock()
    dataset = create_dataset(clock, "org:1", "prj:1", "golden-qa")
    version, _ = create_dataset_version(clock, dataset, "2.0.0")
    version, _ = add_test_case(clock, version, input="case-a", expected="a")
    version, _ = add_test_case(clock, version, input="case-b", expected="b")
    assert version.test_case_count == 2
    removed_id = version.test_cases[0].id
    version, _ = remove_test_case(clock, version, removed_id)
    assert version.test_case_count == 1
    locked, event = lock_dataset_version(clock, version)
    assert event.name == "dataset_version.locked"
    assert locked.test_case_count == 1
