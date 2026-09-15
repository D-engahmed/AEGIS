"""Trace preservation: evaluation traces are immutable evidence and never sampled."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import SpanAttributes, SpanData, TraceRecord


class TracePreservationEngine:
    """Preserve evaluation traces with strict correlation and integrity checks.

    Operational telemetry may be sampled. Any span linked to a run/execution is
    evaluation evidence and therefore cannot be sampled away.
    """

    def __init__(self, preserve: dict[str, TraceRecord] | None = None) -> None:
        self._preserved: dict[str, TraceRecord] = preserve if preserve is not None else {}

    @staticmethod
    def is_evaluation_span(span: SpanData) -> bool:
        attributes = span.attributes
        return bool(
            attributes.get(SpanAttributes.RUN_ID)
            or attributes.get(SpanAttributes.EXECUTION_ID)
        )

    def should_sample(self, span: SpanData, sample_rate: float = 1.0) -> bool:
        """Return whether a span may be sampled out of ordinary telemetry."""
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0.0 and 1.0")
        if self.is_evaluation_span(span):
            return False
        return sample_rate >= 1.0 or _sample(span.trace_id, sample_rate)

    def preserve_evaluation_trace(
        self,
        run_id: str,
        trace_id: str,
        spans: list[SpanData],
    ) -> TraceRecord:
        if not run_id:
            raise ValueError("run_id is required for evaluation evidence")
        if not trace_id:
            raise ValueError("trace_id is required for evaluation evidence")
        if not spans:
            raise ValueError("cannot preserve an empty trace")
        if any(span.trace_id != trace_id for span in spans):
            raise ValueError("all spans in a trace record must share trace_id")

        evaluation_spans = [span for span in spans if self.is_evaluation_span(span)]
        if not evaluation_spans:
            raise ValueError("evaluation trace must contain a run or execution correlation")

        run_ids = {
            str(span.attributes[SpanAttributes.RUN_ID])
            for span in evaluation_spans
            if span.attributes.get(SpanAttributes.RUN_ID)
        }
        if run_ids and run_ids != {run_id}:
            raise ValueError("trace contains spans from multiple run ids")

        execution_ids = [
            str(span.attributes[SpanAttributes.EXECUTION_ID])
            for span in evaluation_spans
            if span.attributes.get(SpanAttributes.EXECUTION_ID)
        ]
        execution_id = execution_ids[0] if execution_ids else None
        if execution_id and any(item != execution_id for item in execution_ids):
            raise ValueError("trace contains multiple execution ids")

        existing = self._preserved.get(trace_id)
        if existing is not None:
            if existing.run_id != run_id or existing.spans != tuple(spans):
                raise ValueError("trace_id already preserved with different evidence")
            return existing

        record = TraceRecord(
            trace_id=trace_id,
            run_id=run_id,
            execution_id=execution_id,
            spans=tuple(spans),
            preserved_at=datetime.now(UTC),
        )
        self._preserved[trace_id] = record
        return record

    def traces_for_run(self, run_id: str) -> list[TraceRecord]:
        return [record for record in self._preserved.values() if record.run_id == run_id]

    def traces_for_execution(self, execution_id: str) -> list[TraceRecord]:
        return [
            record for record in self._preserved.values() if record.execution_id == execution_id
        ]


def _sample(trace_id: str, sample_rate: float) -> bool:
    digest = int(hashlib.sha256(trace_id.encode("utf-8")).hexdigest()[:8], 16)
    return (digest % 1_000_000_000) / 1_000_000_000 < sample_rate


__all__ = ["TracePreservationEngine"]
