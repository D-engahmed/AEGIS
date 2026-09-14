"""Shared fixtures for the contract suite (schema <-> domain <-> SDK parity).

Every test drives the real FastAPI app through the typed SDK over an ASGI
transport, so assertions pin the actual wire contract, not mocks.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from aegis.domain import Role
from aegis.interface.app import create_app
from aegis.interface.container import Container
from aegis_sdk import AegisClient
from tests.conftest import SteppingClock


@pytest.fixture
def api_client() -> tuple[Container, AegisClient]:
    """A (container, SDK client) pair wired through the real app."""
    container = Container(clock=SteppingClock(timedelta(seconds=1)))
    app = create_app(container)
    token = container.auth.issue("user:sdk", "org:1", Role.ADMIN)
    with TestClient(app) as test_client:
        client = AegisClient(
            base_url="http://test",
            token=token,
            http=test_client,
        )
        yield container, client
        client.close()
