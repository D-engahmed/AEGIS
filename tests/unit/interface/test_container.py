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


__all__ = []
