"""Structured JSON logging with correlation id injection."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from .correlation import CorrelationContext
from .models import SpanAttributes


class CorrelationJsonFormatter(logging.Formatter):
    """Formats records as JSON, injecting the active correlation id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": CorrelationContext.get(),
            "service": SpanAttributes.SERVICE_NAME,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "aegis_extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str, sort_keys=True)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a module logger configured with the correlation JSON formatter."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(CorrelationJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


__all__ = ["CorrelationJsonFormatter", "get_logger"]
