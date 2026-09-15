import pytest

from aegis.observability.models import SpanData, SpanStatusCode
from aegis.observability.trace_contract import validate_trace


def span(trace_id: str = "trace:1", run_id: str = "run:1", execution_id: str = "exec:1") -> SpanData:
    return SpanData(
        span_id="span:1",
        name="invoke",
        trace_id=trace_id,
        parent_span_id=None,
        start_time=__import__("datetime").datetime.now(__import__("datetime").UTC),
        end_time=__import__("datetime").datetime.now(__import__("datetime").UTC),
        status=SpanStatusCode.OK,
        attributes={
            "aegis.run.id": run_id,
            "aegis.execution.id": execution_id,
        },
    )


def test_valid_trace_passes() -> None:
    validate_trace("run:1", "trace:1", [span()])


@pytest.mark.parametrize("run_id,trace_id", [("", "trace:1"), ("run:1", "")])
def test_required_identity_is_enforced(run_id: str, trace_id: str) -> None:
    with pytest.raises(ValueError):
        validate_trace(run_id, trace_id, [span()])


def test_empty_trace_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        validate_trace("run:1", "trace:1", [])


def test_mixed_trace_ids_rejected() -> None:
    with pytest.raises(ValueError, match="trace_id"):
        validate_trace("run:1", "trace:1", [span(), span(trace_id="trace:2")])


def test_unrelated_trace_rejected() -> None:
    item = span()
    item.attributes.clear()
    with pytest.raises(ValueError, match="correlation"):
        validate_trace("run:1", "trace:1", [item])


def test_cross_run_trace_rejected() -> None:
    with pytest.raises(ValueError, match="run_id"):
        validate_trace("run:1", "trace:1", [span(), span(run_id="run:2")])


def test_mixed_execution_trace_rejected() -> None:
    with pytest.raises(ValueError, match="execution"):
        validate_trace("run:1", "trace:1", [span(), span(execution_id="exec:2")])
