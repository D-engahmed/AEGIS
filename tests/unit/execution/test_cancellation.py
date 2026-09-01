"""Cooperative cancellation tokens."""

import pytest

from aegis.domain.time import FrozenClock
from aegis.execution.cancellation import CancellationRequested, CancellationToken

pytestmark = pytest.mark.unit


def test_token_is_an_immutable_snapshot() -> None:
    clock = FrozenClock()
    token = CancellationToken("run:1", "alice", clock.now())
    assert token.is_cancelled
    with pytest.raises(CancellationRequested):
        token.raise_if_cancelled()


def test_registry_round_trip() -> None:
    clock = FrozenClock()
    from aegis.infrastructure.memory import InMemoryCancellationRegistry

    registry = InMemoryCancellationRegistry()
    assert not registry.is_cancelled("run:1")
    registry.cancel("run:1", "alice", clock)
    assert registry.is_cancelled("run:1")
    assert registry.who_cancelled("run:1") == "alice"
    assert registry.who_cancelled("run:2") is None
