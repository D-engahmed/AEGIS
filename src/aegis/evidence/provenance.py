"""Provenance builder: pins every versioned input behind a score.

A ProvenanceSnapshot records content-addressed fingerprints of the target
config, dataset, and evaluator configuration at the moment evidence is created,
so a score can always be traced to exactly what produced it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass

from aegis.domain import DatasetVersion, Experiment, TargetVersion
from aegis.domain.time import Clock

from .models import ProvenanceSnapshot


def content_hash(value: object) -> str:
    """Stable SHA-256 over an order-independent serialization of the value."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    return str(value)


def build_provenance(
    clock: Clock,
    experiment: Experiment,
    target_version: TargetVersion,
    dataset_version: DatasetVersion,
    evaluator_identities: Iterable[str],
    policy_version_id: str | None = None,
) -> ProvenanceSnapshot:
    """Assemble the immutable provenance for the experiment's evidence."""
    return ProvenanceSnapshot(
        experiment_id=experiment.id,
        target_version_id=target_version.id,
        target_config_hash=content_hash(target_version.config),
        dataset_version_id=dataset_version.id,
        dataset_hash=content_hash(dataset_version.test_cases),
        evaluator_identities=tuple(sorted(evaluator_identities)),
        evaluator_config_hash=content_hash(experiment.snapshot.settings),
        policy_version_id=policy_version_id or experiment.snapshot.policy_version_id,
        snapshot_timestamp=clock.now(),
    )


__all__ = ["build_provenance", "content_hash"]
