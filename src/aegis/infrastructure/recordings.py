"""Recorded-traffic target adapter and JSONL replay fixture format.

`aegis record` captures real invocations (output, latency, tokens, cost,
trace id) for every test case into a replay fixture. The
`RecordedTrafficTargetClient` plays the fixture back deterministically so an
evaluation can be reproduced offline without reaching the live target — the
transport seam (TargetClient) makes the engine agnostic to the source of
responses (async-execution-contract.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aegis.application.ports import (
    TargetClient,
    TargetInvocation,
    TargetInvocationError,
    TargetInvocationRequest,
)
from aegis.domain import FailureCode

FORMAT = "aegis-record/v1"
_HEADER = {"aegis_record": FORMAT}


@dataclass(frozen=True)
class InvocationRecord:
    """One captured invocation; an error record carries a failure instead."""

    test_case_id: str
    input: Any
    output: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    trace_artifact_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def write_recordings(path: str | Path, records: list[InvocationRecord]) -> None:
    """Persist a fixture: a version header line followed by one JSON record per invocation."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(_HEADER) + "\n")
        for record in records:
            handle.write(json.dumps(asdict(record)) + "\n")


def load_recordings(path: str | Path) -> list[InvocationRecord]:
    records: list[InvocationRecord] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if "aegis_record" in row:
                continue
            records.append(InvocationRecord(**row))
    return records


def _failure_code(code: str) -> FailureCode:
    for candidate in FailureCode:
        if candidate.value == code:
            return candidate
    return FailureCode.UNKNOWN


class RecordedTrafficTargetClient(TargetClient):
    """Deterministic offline adapter backed by a recordings fixture.

    ``match_on`` selects how an invocation request is keyed to a record:
    ``auto`` (default) prefers the recorded ``test_case_id`` then falls back to
    whole-``input`` equality; ``test_case_id`` and ``input`` are strict modes.
    """

    def __init__(self, path: str | Path, *, match_on: str = "auto") -> None:
        self._records = load_recordings(str(path))
        self.match_on = match_on

    def _find(self, request: TargetInvocationRequest) -> InvocationRecord | None:
        by_id: InvocationRecord | None = None
        by_input: InvocationRecord | None = None
        for record in self._records:
            if (
                self.match_on in ("auto", "test_case_id")
                and by_id is None
                and (record.test_case_id == request.test_case_id)
            ):
                by_id = record
            if (
                self.match_on in ("auto", "input")
                and by_input is None
                and (record.input == request.payload)
            ):
                by_input = record
        return by_id if by_id is not None else by_input

    def invoke(self, request: TargetInvocationRequest, timeout_seconds: float) -> TargetInvocation:
        record = self._find(request)
        if record is None:
            raise TargetInvocationError(
                FailureCode.UNKNOWN,
                f"no recorded invocation for test_case_id={request.test_case_id!r}",
            )
        if record.error_code is not None:
            raise TargetInvocationError(
                _failure_code(record.error_code),
                record.error_message or "recorded target failure",
            )
        return TargetInvocation(
            output=record.output or "",
            latency_ms=record.latency_ms or 0.0,
            input_tokens=record.input_tokens or 0,
            output_tokens=record.output_tokens or 0,
            cost_usd=record.cost_usd or 0.0,
            trace_artifact_id=record.trace_artifact_id or "",
        )


__all__ = [
    "FORMAT",
    "InvocationRecord",
    "RecordedTrafficTargetClient",
    "load_recordings",
    "write_recordings",
]
