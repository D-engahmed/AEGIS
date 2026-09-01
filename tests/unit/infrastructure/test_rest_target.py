"""REST target adapter against a real localhost HTTP server (stdlib only)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.application.ports import TargetInvocationError, TargetInvocationRequest
from aegis.domain import FailureCode
from aegis.infrastructure.rest_target import RestTargetClient, _to_float

pytestmark = pytest.mark.unit


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except ValueError:
            return {}

    def do_POST(self):  # noqa: N802
        request = self._read_json()
        case = request.get("test_case_id", "")
        if case == "rate":
            self.send_error(429, "slow down")
        elif case == "boom":
            self.send_error(500, "boom")
        elif case == "denied":
            self.send_error(401, "unauthorized")
        elif case == "bad":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"this is {not json")
        else:
            body = json.dumps(
                {
                    "output": "hello",
                    "latency_ms": 42.0,
                    "input_tokens": 5,
                    "output_tokens": 7,
                    "trace_artifact_id": "trace/abc",
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _request(test_case_id="tc:1"):
    return TargetInvocationRequest(
        test_case_id=test_case_id,
        target_version_id="tvr:1",
        payload={"q": "hi"},
        metadata={"model": "fake"},
    )


def test_invoke_happy_path(base_url) -> None:
    client = RestTargetClient(base_url)
    invocation = client.invoke(_request(), timeout_seconds=5.0)
    assert invocation.output == "hello"
    assert invocation.latency_ms == 42.0
    assert invocation.trace_artifact_id == "trace/abc"
    assert invocation.output_tokens == 7


def test_invoke_rate_limit_maps_to_taxonomy(base_url) -> None:
    client = RestTargetClient(base_url)
    with pytest.raises(TargetInvocationError) as exc_info:
        client.invoke(_request(test_case_id="rate"), timeout_seconds=5.0)
    assert exc_info.value.code is FailureCode.PROVIDER_RATE_LIMIT
    assert "slow down" in exc_info.value.message


def test_invoke_server_error_is_transient(base_url) -> None:
    client = RestTargetClient(base_url)
    with pytest.raises(TargetInvocationError) as exc_info:
        client.invoke(_request(test_case_id="boom"), timeout_seconds=5.0)
    assert exc_info.value.code is FailureCode.TEMPORARY_UNAVAILABLE


def test_invoke_malformed_response(base_url) -> None:
    client = RestTargetClient(base_url)
    with pytest.raises(TargetInvocationError) as exc_info:
        client.invoke(_request(test_case_id="bad"), timeout_seconds=5.0)
    assert exc_info.value.code is FailureCode.MALFORMED_RESPONSE


def test_invoke_401_maps_to_unauthorized(base_url) -> None:
    client = RestTargetClient(base_url)
    with pytest.raises(TargetInvocationError) as exc_info:
        client.invoke(_request(test_case_id="denied"), timeout_seconds=5.0)
    assert exc_info.value.code is FailureCode.UNAUTHORIZED
    assert "unauthorized" in exc_info.value.message


def test_invoke_unreachable_target_maps_to_crash() -> None:
    client = RestTargetClient("http://127.0.0.1:1")
    with pytest.raises(TargetInvocationError) as exc_info:
        client.invoke(_request(), timeout_seconds=0.5)
    assert exc_info.value.code in (FailureCode.TARGET_CRASH, FailureCode.NETWORK_TIMEOUT)


def test_to_float_falls_back() -> None:
    assert _to_float("12.5", 1.0) == 12.5
    assert _to_float(None, 1.0) == 1.0
    assert _to_float("abc", 1.0) == 1.0
