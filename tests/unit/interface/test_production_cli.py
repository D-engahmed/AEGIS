"""Production CLI (container entrypoint): version, probe, worker."""

from __future__ import annotations

import pytest

import aegis
from aegis.cli import main as production_main

pytestmark = pytest.mark.unit


def test_production_cli_version(capsys) -> None:
    assert production_main(["version"]) == 0
    assert capsys.readouterr().out.strip() == aegis.__version__


def test_production_cli_probe(capsys) -> None:
    assert production_main(["probe"]) == 0
    assert "import ok" in capsys.readouterr().out


def test_production_cli_worker_empty_queue(monkeypatch, capsys) -> None:
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("AEGIS_REDIS_URL", raising=False)
    assert production_main(["worker", "--count", "5"]) == 0
    assert capsys.readouterr().out == "processed 0 run(s); 0 pending\n"


__all__ = []
