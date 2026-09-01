"""REST target adapter: HTTP client for a target's /invoke endpoint.

Maps transport failures onto the failure taxonomy so the retry policy can
classify them (std-lib only; the engine only ever sees TargetInvocationError).
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from aegis.application.ports import (
    TargetClient,
    TargetInvocation,
    TargetInvocationError,
    TargetInvocationRequest,
)
from aegis.domain import FailureCode

DEFAULT_INVOKE_PATH = "/invoke"


class RestTargetClient(TargetClient):
    """HTTP adapter. `base_url` is the target origin, e.g. http://localhost:8080."""

    def __init__(
        self,
        base_url: str,
        *,
        invoke_path: str = DEFAULT_INVOKE_PATH,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.invoke_path = invoke_path
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        }

    def _url(self) -> str:
        return f"{self.base_url}{self.invoke_path}"

    def invoke(self, request: TargetInvocationRequest, timeout_seconds: float) -> TargetInvocation:
        started = time.monotonic()
        payload = {
            "test_case_id": request.test_case_id,
            "target_version_id": request.target_version_id,
            "input": request.payload,
            "metadata": request.metadata,
        }
        req = urllib.request.Request(
            self._url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
            elapsed_ms = (time.monotonic() - started) * 1000.0
        except urllib.error.HTTPError as error:
            detail = ""
            try:
                detail = error.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # noqa: BLE001
                detail = ""
            if error.code == 429:
                raise TargetInvocationError(
                    FailureCode.PROVIDER_RATE_LIMIT, f"rate limited: {detail}"
                ) from None
            if error.code in (401, 403):
                raise TargetInvocationError(FailureCode.UNAUTHORIZED, detail) from None
            if error.code >= 500:
                raise TargetInvocationError(
                    FailureCode.TEMPORARY_UNAVAILABLE, f"target error {error.code}: {detail}"
                ) from None
            raise TargetInvocationError(FailureCode.INVALID_CONFIG, detail) from None
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise TargetInvocationError(FailureCode.NETWORK_TIMEOUT, str(reason)) from None
            raise TargetInvocationError(FailureCode.TARGET_CRASH, str(reason)) from None
        except TimeoutError:
            raise TargetInvocationError(FailureCode.NETWORK_TIMEOUT, "target timed out") from None
        except Exception as error:  # noqa: BLE001
            raise TargetInvocationError(FailureCode.UNKNOWN, str(error)) from None

        try:
            data = json.loads(body)
        except ValueError as error:
            raise TargetInvocationError(
                FailureCode.MALFORMED_RESPONSE, f"non-JSON response: {error}"
            ) from None
        if not isinstance(data, dict):
            raise TargetInvocationError(
                FailureCode.MALFORMED_RESPONSE, "response is not a JSON object"
            )
        latency_ms = _to_float(data.get("latency_ms"), elapsed_ms)
        try:
            return TargetInvocation(
                output=str(data.get("output") or ""),
                latency_ms=latency_ms,
                input_tokens=int(data.get("input_tokens") or 0),
                output_tokens=int(data.get("output_tokens") or 0),
                cost_usd=float(data.get("cost_usd") or 0.0),
                trace_artifact_id=data.get("trace_artifact_id") or data.get("trace_id"),
            )
        except (TypeError, ValueError) as error:
            raise TargetInvocationError(FailureCode.MALFORMED_RESPONSE, str(error)) from None


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = ["RestTargetClient"]
