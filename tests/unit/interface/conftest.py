"""Global fakes for interface-layer HTTP tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import fixture

from aegis.domain.time import FrozenClock
from aegis.interface.app import create_app
from aegis.interface.container import Container


@fixture
def container() -> Container:
    return Container(clock=FrozenClock())


@fixture
def client(container: Container) -> TestClient:
    app = create_app(container)
    return TestClient(app)


__all__ = ["client", "container"]
