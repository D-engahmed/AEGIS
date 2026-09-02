"""CLI evaluation workflow (layer 03): end-to-end command surface tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aegis.interface.cli import main

pytestmark = pytest.mark.unit


class _CliHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[str] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))
        output = str(request.get("input", ""))
        _CliHandler.requests.append(request.get("test_case_id", ""))
        body = json.dumps(
            {"output": output, "latency_ms": 3.0, "trace_artifact_id": "trace/cli"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: N802
        return


@pytest.fixture
def base_url() -> str:
    _CliHandler.requests.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CliHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _dataset(tmp_path, cases) -> str:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "name": "cli-qa",
                "test_cases": [{"input": input, "expected": expected} for input, expected in cases],
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_cli_evaluate_run_succeeds(base_url: str, tmp_path, capsys) -> None:
    dataset = _dataset(tmp_path, [("hello", "hello"), ("world", "world")])
    code = main(["evaluate", dataset, "--base-url", base_url])
    assert code == 0
    out = capsys.readouterr().out
    assert "succeeded" in out
    assert "evidence records persisted: 2" in out
    assert len(_CliHandler.requests) == 2


def test_cli_evaluate_json_output(base_url: str, tmp_path, capsys) -> None:
    dataset = _dataset(tmp_path, [("a", "a")])
    code = main(["evaluate", dataset, "--base-url", base_url, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["evidence_count"] == 1
    assert all(result["score"] == 0.0 or result["score"] == 1.0 for result in payload["results"])


def test_cli_requires_command(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


__all__ = []
