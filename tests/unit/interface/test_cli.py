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


class _WrongHandler(BaseHTTPRequestHandler):
    """Returns outputs that never match the goldens (exact_match = 0.0)."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps(
            {"output": "wrong", "latency_ms": 3.0, "trace_artifact_id": "trace/cli/wrong"}
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


@pytest.fixture
def wrong_base_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WrongHandler)
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


def test_cli_evaluate_blocking_gate_emits_verdict(wrong_base_url: str, tmp_path, capsys) -> None:
    dataset = _dataset(tmp_path, [("hello", "hello"), ("world", "world")])
    gates = '[{"metric": "exact_match", "min_value": 0.9}]'
    code = main(["evaluate", dataset, "--base-url", wrong_base_url, "--json", "--gates", gates])
    assert code == 0  # a blocked run is still a completed run
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert all(result["score"] == 0.0 for result in payload["results"])
    assert payload["gate"]["verdict"] == "block"
    assert payload["gate"]["is_blocked"] is True
    decisions = {d["gate_id"]: d for d in payload["gate"]["decisions"]}
    assert decisions["dim/exact_match"]["verdict"] == "fail"
    assert decisions["dim/exact_match"]["severity"] == "high"


def test_cli_evaluate_gates_from_file(tmp_path, capsys, base_url: str) -> None:
    dataset = _dataset(tmp_path, [("a", "a")])
    gates_file = tmp_path / "gates.json"
    gates_file.write_text('[{"gate_id": "qa/exact", "metric": "exact_match", "max_value": 1.0}]')
    code = main(["evaluate", dataset, "--base-url", base_url, "--json", "--gates", str(gates_file)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate"]["verdict"] == "pass"
    assert payload["gate"]["is_blocked"] is False


def test_cli_worker_empty_queue(capsys) -> None:
    code = main(["worker", "--json"])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"processed": 0, "pending": 0}


def test_cli_worker_watch_loops_until_interrupt(monkeypatch, capsys) -> None:
    calls: dict[str, int] = {"n": 0}

    def fake_drain(cli, count=None) -> int:
        calls["n"] += 1
        if calls["n"] >= 3:
            raise KeyboardInterrupt
        return 0

    monkeypatch.setattr("aegis.interface.cli.drain_queue", fake_drain)
    code = main(["worker", "--watch", "--poll-seconds", "0.01"])
    assert code == 0
    assert calls["n"] == 3
    out = capsys.readouterr().out
    assert out.count("processed 0 run(s)") == 2


def test_cli_worker_one_shot_reports_poison(capsys, monkeypatch) -> None:
    """A job that escapes the engine's retry envelope fails fast with exit 1."""

    def bad_drain(cli, count=None) -> int:
        raise RuntimeError("bad target config")

    monkeypatch.setattr("aegis.interface.cli.drain_queue", bad_drain)
    code = main(["worker", "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "bad target config"


def test_cli_worker_watch_survives_poison(monkeypatch, capsys) -> None:
    """Watch mode reports the poisoned job, redelivers it, keeps polling."""
    calls: dict[str, int] = {"n": 0}

    def fake_drain(cli, count=None) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("bad target config")
        if calls["n"] >= 3:
            raise KeyboardInterrupt
        return 0

    monkeypatch.setattr("aegis.interface.cli.drain_queue", fake_drain)
    code = main(["worker", "--watch", "--poll-seconds", "0.01"])
    assert code == 0
    assert calls["n"] == 3
    out = capsys.readouterr().out
    assert "worker error (job abandoned): bad target config" in out
    assert out.count("processed 0 run(s)") == 1


def test_cli_requires_command(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


__all__ = []
