"""Trace preservation: evaluation traces are evidence and are never sampled."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aegis.application.run_tracing import TracePayload, TraceSpanPayload, TraceStore

from .models import SpanAttributes, SpanData, TraceRecord


class TracePreservationEngine:
    """Keeps every evaluation-linked trace and rejects sampling for them.

    A span is evaluation evidence when it carries a run or execution id attribute.
    Production operational spans may be sampled normally; evaluation spans never are.
    """

    def __init__(
        self,
        preserve: dict[str, TraceRecord] | None = None,
        store: TraceStore | None = None,
    ) -> None:
        self._preserved: dict[str, TraceRecord] = preserve if preserve is not None else {}
        self._store = store

    @staticmethod
    def is_evaluation_span(span: SpanData) -> bool:
        attributes = set(span.attributes)
        return SpanAttributes.RUN_ID in attributes or SpanAttributes.EXECUTION_ID in attributes

    def should_sample(self, span: SpanData, sample_rate: float = 1.0) -> bool:
        """False when the span must be preserved (evaluation), else the rate applies."""
        if self.is_evaluation_span(span):
            return False
        return sample_rate >= 1.0 or _sample(span.trace_id, sample_rate)

    def preserve_evaluation_trace(
        self,
        run_id: str,
        trace_id: str,
        spans: list[SpanData],
    ) -> TraceRecord:
        evaluation_spans = [span for span in spans if self.is_evaluation_span(span)]
        execution_ids = [
            str(span.attributes[SpanAttributes.EXECUTION_ID])
            for span in evaluation_spans
            if SpanAttributes.EXECUTION_ID in span.attributes
        ]
        record = TraceRecord(
            trace_id=trace_id,
            run_id=run_id,
            execution_id=execution_ids[0] if execution_ids else None,
            spans=tuple(spans),
            preserved_at=datetime.now(UTC),
        )
        self._preserved[trace_id] = record
        if self._store is not None:
            self._store.persist(_payload_from_record(record))
        return record

    def traces_for_run(self, run_id: str) -> list[TraceRecord]:
        if self._store is not None:
            return [_record_from_payload(payload) for payload in self._store.list_for_run(run_id)]
        return [record for record in self._preserved.values() if record.run_id == run_id]

    def traces_for_execution(self, execution_id: str) -> list[TraceRecord]:
        if self._store is not None:
            return [
                _record_from_payload(payload)
                for payload in self._store.list_for_execution(execution_id)
            ]
        return [
            record for record in self._preserved.values() if record.execution_id == execution_id
        ]


def _payload_from_record(record: TraceRecord) -> TracePayload:
    return TracePayload(
        trace_id=record.trace_id,
        run_id=record.run_id,
        execution_id=record.execution_id,
        preserved_at=record.preserved_at,
        spans=tuple(
            TraceSpanPayload(
                span_id=span.span_id,
                name=span.name,
                trace_id=span.trace_id,
                parent_span_id=span.parent_span_id,
                start_time=span.start_time,
                end_time=span.end_time,
                status=span.status.value,
                attributes=dict(span.attributes),
            )
            for span in record.spans
        ),
    )


def _record_from_payload(payload: TracePayload) -> TraceRecord:
    from .models import SpanStatusCode

    return TraceRecord(
        trace_id=payload.trace_id,
        run_id=payload.run_id,
        execution_id=payload.execution_id,
        preserved_at=payload.preserved_at,
        spans=tuple(
            SpanData(
                span_id=span.span_id,
                name=span.name,
                trace_id=span.trace_id,
                parent_span_id=span.parent_span_id,
                start_time=span.start_time,
                end_time=span.end_time,
                status=SpanStatusCode(span.status),
                attributes=dict(span.attributes),
            )
            for span in payload.spans
        ),
    )


def _sample(trace_id: str, sample_rate: float) -> bool:
    digest = int(hashlib.sha256(trace_id.encode("utf-8")).hexdigest()[:8], 16)
    return (digest % 1_000_000_000) / 1_000_000_000 < sample_rate


__all__ = ["TracePreservationEngine"]
