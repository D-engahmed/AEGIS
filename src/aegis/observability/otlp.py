"""OTLP/HTTP exporter: sends AEGIS spans to an OpenTelemetry Collector.

Implements the ``TelemetryExporter`` boundary (tracing.py) as a batching
exporter speaking the OTLP/HTTP JSON protocol (``Content-Type: application/json``,
``POST <endpoint>/v1/traces``). No protobuf or OTel SDK dependency is required;
purely mechanical spans are mapped onto the protobuf JSON shape the Collector
accepts. Evaluation traces are still preserved locally (they are evidence); the
Collector stream is a separate export, not a replacement.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

import httpx

from .models import SpanAttributes, SpanData, SpanStatusCode
from .tracing import TelemetryExporter

DEFAULT_ENDPOINT = "http://localhost:4318"
_MAX_BATCH = 64


def _to_base64(value: str) -> str:
    try:
        return base64.b64encode(bytes.fromhex(value)).decode("ascii")
    except ValueError:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _unix_nanos(value: datetime) -> str:
    return str(int(value.timestamp() * 1_000_000_000))


def _attribute(value: Any) -> dict[str, Any] | None:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list | tuple):
        return {"arrayValue": {"values": [v for v in (_attribute(item) for item in value) if v]}}
    if isinstance(value, dict):
        return {
            "kvlistValue": {
                "values": [
                    {"key": str(key), "value": encoded}
                    for key, raw in value.items()
                    if (encoded := _attribute(raw)) is not None
                ]
            }
        }
    return None


def _span_to_otlp(span: SpanData) -> dict[str, Any]:
    attributes = [
        {"key": key, "value": encoded}
        for key, raw in span.attributes.items()
        if (encoded := _attribute(raw)) is not None
    ]
    payload: dict[str, Any] = {
        "traceId": _to_base64(span.trace_id),
        "spanId": _to_base64(span.span_id),
        "name": span.name,
        "kind": 1,  # span kind INTERNAL
        "startTimeUnixNano": _unix_nanos(span.start_time),
        "endTimeUnixNano": _unix_nanos(span.end_time),
        "attributes": attributes,
        "status": (
            {"code": 2, "message": "error"}
            if span.status is SpanStatusCode.ERROR
            else {"code": 1}
        ),
    }
    if span.parent_span_id is not None:
        payload["parentSpanId"] = _to_base64(span.parent_span_id)
    return payload


def _traces_payload(spans: list[SpanData], service_name: str) -> dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}}
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "aegis"},
                        "spans": [_span_to_otlp(span) for span in spans],
                    }
                ],
            }
        ]
    }


class OtlpSpanExporter(TelemetryExporter):
    """Synchronous, buffering OTLP/HTTP exporter with threshold+explicit flush.

    Spans are buffered and sent as batches. A failed request keeps its spans in
    the buffer for the next flush; ``flush()`` never raises, it reports failure.
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        service_name: str = SpanAttributes.SERVICE_NAME,
        client: httpx.Client | None = None,
        max_batch: int = _MAX_BATCH,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._service_name = service_name
        self._max_batch = max_batch
        self._client = client or httpx.Client(timeout=5.0)
        self._buffer: list[SpanData] = []
        self.failed_batches: int = 0
        self.exported_batches: int = 0

    def export_span(self, span_data: SpanData) -> None:
        self._buffer.append(span_data)
        if len(self._buffer) >= self._max_batch:
            self.flush()

    def flush(self) -> bool:
        """POST the buffered spans; returns True when the batch was accepted."""
        if not self._buffer:
            return True
        batch, self._buffer = self._buffer, []
        response: httpx.Response | None = None
        try:
            response = self._client.post(
                f"{self._endpoint}/v1/traces",
                headers={"Content-Type": "application/json"},
                content=json.dumps(_traces_payload(batch, self._service_name)),
            )
            if 200 <= response.status_code < 300:
                self.exported_batches += 1
                return True
            self.failed_batches += 1
        except httpx.HTTPError:
            self.failed_batches += 1
        self._buffer.extend(batch)  # redelivery on next flush
        if response is not None:
            response.close()
        return False

    def shutdown(self) -> None:
        self.flush()
        self._client.close()

    @property
    def buffered(self) -> int:
        return len(self._buffer)


__all__ = ["DEFAULT_ENDPOINT", "OtlpSpanExporter"]