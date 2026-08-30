"""Unit tests for clocks, events and the source/target registry."""

from datetime import UTC, datetime

import pytest

from aegis.domain.events import (
    dataset_version_locked,
    emit,
    organization_created,
    project_created,
    target_version_referenced,
)
from aegis.domain.exceptions import NotFound
from aegis.domain.registry import (
    annex_target,
    register_source,
    require_registered,
)
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.domain.time import FrozenClock, SystemClock

pytestmark = pytest.mark.unit


def test_system_clock_is_utc_naive() -> None:
    value = SystemClock().now()
    assert value.tzinfo is UTC
    assert (datetime.now(UTC) - value).total_seconds() < 5


def test_frozen_clock_is_deterministic() -> None:
    clock = FrozenClock()
    assert clock.now() == clock.now()
    pinned = datetime(2026, 1, 1, tzinfo=UTC)
    assert FrozenClock(pinned).now() == pinned


def test_emit_builds_immutable_event() -> None:
    clock = FrozenClock()
    event = emit(clock, "test.run", "Experiment", "exp:1", status="queued")
    assert event.name == "test.run"
    assert event.aggregate_type == "Experiment"
    assert event.payload == {"status": "queued"}
    assert event.event_id.startswith("evt:")


def test_event_constructors() -> None:
    clock = FrozenClock()
    assert organization_created(clock, "org:1", "ACME", "u").name == "organization.created"
    assert project_created(clock, "prj:1", "org:1", "core", "u").name == "project.created"
    assert dataset_version_locked(clock, "dsv:1", "ds:1", "u").name == "dataset_version.locked"
    assert (
        target_version_referenced(clock, "tvr:1", "tgt:1", "dsv:1").name
        == "target_version.referenced"
    )


def test_registry_annex_marks_target_referenced() -> None:
    clock = FrozenClock()
    reference = register_source(clock, "org:1", "prj:1", "dsv:1", "u-eng")
    target = create_target(clock, "org:1", "prj:1", "router", TargetType.LLM_APPLICATION)
    version = create_target_version(clock, target, "1.0.0", {"model": "gpt-x"})
    updated, referenced, event = annex_target(clock, reference, version)
    assert event.name == "target_version.referenced"
    assert "tvr" in referenced.id
    assert referenced.referenced is True
    assert updated.target_version_ids == (referenced.id,)
    require_registered(updated, "dsv:1")
    with pytest.raises(NotFound):
        require_registered(updated, "dsv:2")
    # annex is idempotent
    updated2, _, _ = annex_target(clock, updated, referenced)
    assert updated2.target_version_ids == (referenced.id,)
