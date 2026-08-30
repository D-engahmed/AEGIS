"""Unit tests for targets and target version immutability (entity group E2)."""

import pytest

from aegis.domain.exceptions import ImmutableResourceViolation, ValidationFailed
from aegis.domain.identifiers import VersionLabel, valid_id
from aegis.domain.targets import (
    Target,
    TargetType,
    create_target,
    create_target_version,
    ensure_mutable,
)
from aegis.domain.time import FrozenClock

pytestmark = pytest.mark.unit


def _target(clock: FrozenClock) -> Target:
    return create_target(clock, "org:1", "prj:1", "llm-router", TargetType.LLM_APPLICATION)


def test_create_target_version_snapshot() -> None:
    clock = FrozenClock()
    target = _target(clock)
    version = create_target_version(
        clock,
        target,
        "v1.2.3",
        {"model": "gpt-x", "prompt": "…", "tools": ["search"]},
        commit_sha="abc123",
    )
    assert version.id.startswith("tvr:")
    assert str(version.label) == "v1.2.3"
    assert version.config["model"] == "gpt-x"
    snap = version.snapshot()
    assert snap["label"] == "v1.2.3"
    assert snap["commit_sha"] == "abc123"
    assert snap["referenced"] is False


def test_version_config_rejects_invalid_map() -> None:
    clock = FrozenClock()
    target = _target(clock)
    with pytest.raises(ValidationFailed):
        create_target_version(clock, target, "v1.0.0", {1: "not-a-string-key"})
    with pytest.raises(ValidationFailed):
        create_target_version(clock, target, "v1.0.0", {"bad": float("nan")})


def test_referenced_version_is_immutable() -> None:
    clock = FrozenClock()
    target = _target(clock)
    version = create_target_version(clock, target, "1.0.0", {"model": "gpt-x"})
    referenced = version.mark_referenced()
    assert referenced.referenced is True
    assert referenced is not version
    with pytest.raises(ImmutableResourceViolation):
        ensure_mutable(referenced)
    ensure_mutable(version)


def test_version_order_and_normalization() -> None:
    assert VersionLabel("2.0") > VersionLabel("1.9.9")
    assert VersionLabel("1.2.3") == VersionLabel("v1.2.3")
    assert VersionLabel("1").patch == 0
    with pytest.raises(ValueError):
        VersionLabel("1.2.x")
    with pytest.raises(ValueError):
        VersionLabel("")


def test_valid_id_shape() -> None:
    assert valid_id("org:3f2a91c4b6d0")
    assert not valid_id("nope")
    assert not valid_id("org:has spaces")
