"""Production CLI (container entrypoint): version, probe, worker on the interface CLI."""

from __future__ import annotations

import pytest

import aegis
from aegis.interface.cli import main as production_main

pytestmark = pytest.mark.unit


def test_production_cli_version(capsys) -> None:
    assert production_main(["version"]) == 0
    assert capsys.readouterr().out.strip() == aegis.__version__


def test_production_cli_probe_unconfigured(capsys, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("AEGIS_REDIS_URL", raising=False)
    assert production_main(["probe"]) == 0
    assert "import ok" in capsys.readouterr().out


def test_production_cli_probe_reports_store_failures(capsys, monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:1/aegis")
    monkeypatch.setenv("AEGIS_REDIS_URL", "redis://127.0.0.1:1/0")

    def boom(url: str) -> None:
        raise ConnectionError("refused")

    monkeypatch.setattr("aegis.interface.cli._database_reachable", boom)
    monkeypatch.setattr("aegis.interface.cli._queue_reachable", boom)
    assert production_main(["probe"]) == 1
    out = capsys.readouterr().out
    assert "UNHEALTHY" in out
    assert "database unreachable" in out
    assert "queue unreachable" in out


def test_production_cli_probe_reports_stores_ok(capsys, monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:1/aegis")
    monkeypatch.setenv("AEGIS_REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setattr("aegis.interface.cli._database_reachable", lambda url: None)
    monkeypatch.setattr("aegis.interface.cli._queue_reachable", lambda url: None)
    assert production_main(["probe"]) == 0
    out = capsys.readouterr().out
    assert "import ok" in out
    assert "2 store(s) reachable" in out


def test_production_cli_worker_empty_queue(monkeypatch, capsys) -> None:
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("AEGIS_REDIS_URL", raising=False)
    assert production_main(["worker", "--count", "5"]) == 0
    assert capsys.readouterr().out == "processed 0 run(s); 0 pending\n"
