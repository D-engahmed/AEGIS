"""Failure taxonomy and retry classification (failure-architecture.md).

Every failure is assigned a code from the taxonomy and classified into one of
three retry classes before any retry decision is made:
- DETERMINISTIC: guaranteed to reproduce identically on retry; not retried.
- NON_RETRYABLE: no plausible chance of success on retry, or retry is unsafe.
- RETRYABLE: transient; retried subject to the bounded backoff policy.
"""

from __future__ import annotations

from enum import StrEnum


class FailureClass(StrEnum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    DETERMINISTIC = "deterministic"

    @property
    def retryable(self) -> bool:
        return self is FailureClass.RETRYABLE


class FailureCode(StrEnum):
    """Machine-readable failure taxonomy (failure-architecture.md)."""

    NETWORK_TIMEOUT = "network_timeout"
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    TARGET_CRASH = "target_crash"

    INVALID_CONFIG = "invalid_config"
    SCHEMA_MISMATCH = "schema_mismatch"
    UNAUTHORIZED = "unauthorized"

    AGENT_LOOP = "agent_loop"
    TEST_TIMEOUT = "test_timeout"
    TARGET_TIMEOUT = "target_timeout"
    EXPERIMENT_TIMEOUT = "experiment_timeout"

    INFRASTRUCTURE = "infrastructure"
    SECRET_INCIDENT = "secret_incident"

    UNKNOWN = "unknown"


_RETRYABLE_CODES = {
    FailureCode.NETWORK_TIMEOUT,
    FailureCode.PROVIDER_RATE_LIMIT,
    FailureCode.TEMPORARY_UNAVAILABLE,
    FailureCode.TARGET_CRASH,
    FailureCode.INFRASTRUCTURE,
}

_DETERMINISTIC_CODES = {
    FailureCode.SCHEMA_MISMATCH,
    FailureCode.INVALID_CONFIG,
    FailureCode.UNAUTHORIZED,
}

_NON_RETRYABLE_CODES = {
    FailureCode.MALFORMED_RESPONSE,
    FailureCode.AGENT_LOOP,
    FailureCode.TEST_TIMEOUT,
    FailureCode.TARGET_TIMEOUT,
    FailureCode.EXPERIMENT_TIMEOUT,
    FailureCode.SECRET_INCIDENT,
}


def classify_failure(code: FailureCode) -> FailureClass:
    """Map a failure code to its retry class."""
    if code in _RETRYABLE_CODES:
        return FailureClass.RETRYABLE
    if code in _DETERMINISTIC_CODES:
        return FailureClass.DETERMINISTIC
    if code in _NON_RETRYABLE_CODES:
        return FailureClass.NON_RETRYABLE
    return FailureClass.NON_RETRYABLE


def is_retryable(code: FailureCode) -> bool:
    return classify_failure(code) is FailureClass.RETRYABLE


__all__ = ["FailureClass", "FailureCode", "classify_failure", "is_retryable"]
