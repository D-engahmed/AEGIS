"""Identity value objects: namespaced ids and ordered version labels."""

from __future__ import annotations

import re
import uuid

_SEPARATOR = ":"
_PREFIX_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")
_TAIL_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def new_id(prefix: str) -> str:
    """Generate a namespaced id such as 'org:3f2a91c4b6d0'."""
    if not _PREFIX_RE.fullmatch(prefix):
        raise ValueError(f"invalid id prefix: {prefix!r}")
    return f"{prefix}{_SEPARATOR}{uuid.uuid4().hex[:12]}"


def valid_id(value: str) -> bool:
    """True when the value is a namespaced id with a well-formed tail."""
    if _SEPARATOR not in value:
        return False
    prefix, tail = value.split(_SEPARATOR, 1)
    return _PREFIX_RE.fullmatch(prefix) is not None and _TAIL_RE.fullmatch(tail) is not None


class VersionLabel:
    """Immutable 'major.minor.patch' label with total ordering.

    Accepts '1', '1.2' and '1.2.3' (optionally prefixed with 'v').
    """

    __slots__ = ("_value", "_segments")

    def __init__(self, value: str) -> None:
        raw = value.strip()
        normalized = raw[1:] if raw.startswith("v") else raw
        parts = normalized.split(".")
        if len(parts) not in (1, 2, 3) or any(not part.isdigit() for part in parts):
            raise ValueError(f"invalid version label: {value!r}")
        integers = tuple(int(part) for part in parts)
        self._segments = integers + (0,) * (3 - len(integers))
        self._value = raw

    @property
    def major(self) -> int:
        return self._segments[0]

    @property
    def minor(self) -> int:
        return self._segments[1]

    @property
    def patch(self) -> int:
        return self._segments[2]

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"VersionLabel({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VersionLabel) and self._segments == other._segments

    def __lt__(self, other: VersionLabel) -> bool:
        return self._segments < other._segments

    def __le__(self, other: object) -> bool:
        return isinstance(other, VersionLabel) and self._segments <= other._segments

    def __hash__(self) -> int:
        return hash(self._segments)


__all__ = ["VersionLabel", "new_id", "valid_id"]
