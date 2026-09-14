"""Run mappers: application DTOs to wire schemas."""

from __future__ import annotations

from dataclasses import asdict

from ..schemas import RunOut


def run_out(view) -> RunOut:
    """Map a RunView application DTO to its wire representation."""
    return RunOut(**asdict(view))


__all__ = ["run_out"]
