"""Recorded-traffic fixture round-trip and replay adapter behavior."""

from __future__ import annotations

import pytest

from aegis.application.ports import (
    TargetInvocationError,
    TargetInvocationRequest,
)
from aegis.domain import FailureCode
from aegis.infrastructure.recordings import (
    InvocationRecord,
    RecordedTrafficTargetClient,
    load_recordings,
    write_recordings,
)

pytestmark = pytest.mark.unit


def _records() -> list[InvocationRecord]:
    return [
        InvocationRecord(
            test_case_id="tc:1",
            input="hello",
            output="hello",
            latency_ms=3.0,
            input_tokens=4,
            output_tokens=5,
            cost_usd=0.002,
            trace_artifact_id="trace/1",
        ),
        InvocationRecord(
            test_case_id="tc:2",
            input="world",
            error_code="provider_rate_limit",
            error_message="slow down",
        ),
    ]


def _request(case_id: str, payload: object) -> TargetInvocationRequest:
    return TargetInvocationRequest(
        test_case_id=case_id,
        target_version_id="tv:1",
        payload=payload,
        metadata={},
    )


def test_fixture_round_trip_and_header_version(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert '"aegis_record": "aegis-record/v1"' in lines[0]
    assert len(lines) == 3
    loaded = load_recordings(path)
    assert [r.test_case_id for r in loaded] == ["tc:1", "tc:2"]
    assert loaded[0].output == "hello"
    assert loaded[1].error_code == "provider_rate_limit"


def test_replay_returns_recorded_invocation(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    client = RecordedTrafficTargetClient(path)
    result = client.invoke(_request("tc:1", "hello"), timeout_seconds=5)
    assert result.output == "hello"
    assert result.latency_ms == 3.0
    assert result.input_tokens == 4
    assert result.output_tokens == 5
    assert result.cost_usd == 0.002
    assert result.trace_artifact_id == "trace/1"


def test_replay_raises_recorded_error(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    client = RecordedTrafficTargetClient(path)
    with pytest.raises(TargetInvocationError) as exc:
        client.invoke(_request("tc:2", "world"), timeout_seconds=5)
    assert exc.value.code is FailureCode.PROVIDER_RATE_LIMIT
    assert exc.value.message == "slow down"


def test_replay_missing_case_is_fatal_deterministic(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    client = RecordedTrafficTargetClient(path)
    with pytest.raises(TargetInvocationError) as exc:
        client.invoke(_request("tc:missing", "nope"), timeout_seconds=5)
    assert exc.value.code is FailureCode.UNKNOWN
    assert "no recorded invocation" in exc.value.message


def test_replay_match_on_input(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    client = RecordedTrafficTargetClient(path, match_on="input")
    result = client.invoke(_request("different-id", "hello"), timeout_seconds=5)
    assert result.output == "hello"


def test_replay_auto_falls_back_to_input_when_ids_differ(tmp_path) -> None:
    path = tmp_path / "rec.jsonl"
    write_recordings(path, _records())
    client = RecordedTrafficTargetClient(path)
    result = client.invoke(_request("tc:brand-new-id", "hello"), timeout_seconds=5)
    assert result.output == "hello"
    assert result.trace_artifact_id == "trace/1"


__all__ = []
