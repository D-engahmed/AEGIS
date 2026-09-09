"""Container wiring: configured policy gates reach the run gate service."""

from __future__ import annotations

import pytest

from aegis.interface.container import Container
from aegis.policy.application import ThresholdGate

pytestmark = pytest.mark.unit


def test_container_run_gates_are_configurable() -> None:
    c = Container(gates=(ThresholdGate("dim/x", "metric", min_value=1.0),))
    assert isinstance(c.run_gates, object)
    assert c.runner is not None


def test_container_default_run_gates_empty() -> None:
    c = Container()
    assert len(c.run_gates._gates) == 0  # noqa: SLF001


def test_container_from_env_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("AEGIS_REDIS_URL", raising=False)
    c = Container.from_env()
    assert type(c.experiments).__name__ == "MemoryExperimentRepository"
    assert type(c.queue).__name__ == "MemoryQueue"


def test_container_from_env_env_wins_over_default(monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:5433/aegis")
    monkeypatch.setenv("AEGIS_REDIS_URL", "redis://127.0.0.1:6380/0")
    c = Container.from_env(migrate=False)
    assert type(c.experiments).__name__ == "PostgresExperimentRepository"
    assert type(c.queue).__name__ == "RedisQueue"


def test_container_from_env_explicit_none_forces_memory(monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:5433/aegis")
    c = Container.from_env(database_url=None, migrate=False)
    assert type(c.experiments).__name__ == "MemoryExperimentRepository"


__all__ = []
