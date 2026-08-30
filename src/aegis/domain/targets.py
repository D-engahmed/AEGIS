"""Targets (entity group E2): applications under evaluation and immutable versions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from .exceptions import ImmutableResourceViolation, ValidationFailed
from .identifiers import VersionLabel, new_id
from .time import Clock


class TargetType(StrEnum):
    LLM_APPLICATION = "llm_application"
    RAG_PIPELINE = "rag_pipeline"
    AGENT = "agent"
    MULTI_AGENT = "multi_agent"
    MODEL_API = "model_api"
    CLASSIFIER = "classifier"


@dataclass(frozen=True)
class Target:
    id: str
    organization_id: str
    project_id: str
    name: str
    target_type: TargetType
    created_at: datetime


@dataclass(frozen=True)
class TargetVersion:
    """An immutable configuration snapshot of a target.

    Once referenced by an experiment the version is structurally immutable:
    see ensure_mutable(). The config captures full provenance for the release
    metadata portion of the experiment cycle.
    """

    id: str
    target_id: str
    organization_id: str
    project_id: str
    label: VersionLabel
    config: Mapping[str, Any]
    created_at: datetime
    commit_sha: str | None = None
    image_digest: str | None = None
    referenced: bool = False

    def snapshot(self) -> dict[str, Any]:
        """Serializable representation of the version."""
        return {
            "id": self.id,
            "target_id": self.target_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "label": str(self.label),
            "config": dict(self.config),
            "commit_sha": self.commit_sha,
            "image_digest": self.image_digest,
            "referenced": self.referenced,
        }

    def mark_referenced(self) -> TargetVersion:
        """Return a copy flagged as referenced (idempotent)."""
        if self.referenced:
            return self
        return replace(self, referenced=True)


def ensure_mutable(version: TargetVersion) -> None:
    """Reject any modification of a version that is already referenced."""
    if version.referenced:
        raise ImmutableResourceViolation(
            f"target version {version.id!r} is referenced and cannot be modified"
        )


def create_target(
    clock: Clock,
    organization_id: str,
    project_id: str,
    name: str,
    target_type: TargetType,
) -> Target:
    """Create a target application record."""
    if not name or not name.strip():
        raise ValidationFailed("target name must not be empty")
    return Target(
        id=new_id("tgt"),
        organization_id=organization_id,
        project_id=project_id,
        name=name.strip(),
        target_type=target_type,
        created_at=clock.now(),
    )


def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Config must be a mapping of non-empty string keys to JSON values."""
    if not isinstance(config, Mapping):
        raise ValidationFailed("target version config must be a mapping")
    for key in config:
        if not isinstance(key, str) or not key:
            raise ValidationFailed("target version config keys must be non-empty strings")
    try:
        return dict(json.loads(json.dumps(dict(config), allow_nan=False)))
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(f"target version config is not JSON-serializable: {exc}") from exc


def create_target_version(
    clock: Clock,
    target: Target,
    label: str | VersionLabel,
    config: Mapping[str, Any],
    commit_sha: str | None = None,
    image_digest: str | None = None,
) -> TargetVersion:
    """Snapshot a target configuration as a new immutable version."""
    parsed = label if isinstance(label, VersionLabel) else VersionLabel(label)
    return TargetVersion(
        id=new_id("tvr"),
        target_id=target.id,
        organization_id=target.organization_id,
        project_id=target.project_id,
        label=parsed,
        config=_validate_config(config),
        created_at=clock.now(),
        commit_sha=commit_sha,
        image_digest=image_digest,
    )


__all__ = [
    "Target",
    "TargetType",
    "TargetVersion",
    "create_target",
    "create_target_version",
    "ensure_mutable",
]
