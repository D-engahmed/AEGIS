"""Migration runner CLI surface (layer 02 infrastructure)."""

from __future__ import annotations

import pytest

from aegis.infrastructure.migrations import main

pytestmark = pytest.mark.unit


def test_migrations_main_requires_dsn(capsys) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out


def test_migrations_main_rejects_extra_args(capsys) -> None:
    assert main(["dsn", "extra"]) == 2
    assert "usage" in capsys.readouterr().out


__all__ = []
