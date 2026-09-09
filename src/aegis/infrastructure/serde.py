"""JSON (de)serialization for domain aggregates stored in PostgreSQL jsonb columns.

The domain layer is std-lib only; infrastructure needs a lossless, reversible
mapping for nested frozen dataclasses (snapshots, evidence, provenance, gate
reports). Datetimes and version labels are marked so they round-trip exactly.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from enum import Enum

from aegis.domain.identifiers import VersionLabel

_DT = "$dt"
_VER = "$ver"


def to_json(value) -> str:
    """Serialize a domain value (or nested structure) to a JSON string."""
    return json.dumps(to_plain(value))


def from_json(blob: str | None):
    """Deserialize a JSON string back to plain values with markers restored."""
    if blob is None:
        return None
    return from_plain(json.loads(blob))


def to_plain(value):
    """Convert a domain value to plain JSON-able structures (markers intact)."""
    return _encode(value)


def from_plain(value):
    """Restore datetimes/version labels from plain structures produced by to_plain."""
    return _decode(value)


def _encode(value):
    if dataclasses.is_dataclass(value):
        return {_encode(k): _encode(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, datetime):
        return {_DT: value.isoformat()}
    if isinstance(value, VersionLabel):
        return {_VER: str(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {_encode(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, set)):
        return [_encode(item) for item in value]
    return value


def _decode(value):
    if isinstance(value, dict):
        if _DT in value and len(value) == 1:
            return datetime.fromisoformat(value[_DT])
        if _VER in value and len(value) == 1:
            return VersionLabel(value[_VER])
        return {_decode(k): _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


__all__ = ["from_json", "from_plain", "to_json", "to_plain"]
