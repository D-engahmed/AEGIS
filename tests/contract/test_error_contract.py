"""Error contract: HTTP failures map to stable SDK exception types.

The API returns a uniform ``{"detail": str}`` envelope; the SDK translates
status codes via ``AegisErrorMapping``. This pins the table so neither side
can change it unnoticed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aegis.domain import Role
from aegis.interface.app import create_app
from aegis_sdk import (
    AegisClient,
    AegisError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

pytestmark = pytest.mark.contract


def test_status_code_to_exception_table() -> None:
    from aegis_sdk.errors import AegisErrorMapping as mapping

    assert mapping.for_status(401) is AuthorizationError
    assert mapping.for_status(403) is AuthorizationError
    assert mapping.for_status(404) is NotFoundError
    assert mapping.for_status(422) is ValidationError
    assert mapping.for_status(409) is ConflictError
    from aegis_sdk import ServerError

    assert mapping.for_status(500) is ServerError
    assert mapping.for_status(503) is ServerError
    assert issubclass(AuthorizationError, AegisError)
    assert issubclass(NotFoundError, AegisError)
    assert issubclass(ValidationError, AegisError)
    assert issubclass(ConflictError, AegisError)
    assert issubclass(ServerError, AegisError)


def test_unknown_resources_raise_not_found(api_client) -> None:
    _, client = api_client
    with pytest.raises(NotFoundError):
        client.runs.get("run:nope")
    with pytest.raises(NotFoundError):
        client.policy.verdict("run:nope")
    with pytest.raises(NotFoundError):
        client.catalog.get_target("tvr:nope")
    with pytest.raises(NotFoundError):
        client.experiments.get("exp:nope")


def test_viewer_cannot_cancel_runs(api_client) -> None:
    container, _ = api_client
    viewer = AegisClient(
        base_url="http://test",
        token=container.auth.issue("user:viewer", "org:1", Role.VIEWER),
        http=TestClient(create_app(container)),
    )
    try:
        with pytest.raises(AuthorizationError):
            viewer.runs.cancel("run:any")
    finally:
        viewer.close()


def test_invalid_payloads_raise_validation_error(api_client) -> None:
    _, client = api_client
    with pytest.raises(ValidationError):
        client.catalog.register_target("prj:1", "bad", config=[1, 2, 3])


def test_double_start_raises_conflict(api_client) -> None:
    _, client = api_client
    target = client.catalog.register_target("prj:1", "conflict-target")
    dataset = client.catalog.register_dataset("prj:1", "conflict-qa")
    experiment = client.experiments.create(
        "prj:1",
        "conflict-eval",
        snapshot={
            "target_version_id": target.id,
            "dataset_version_id": dataset.id,
            "evaluator_version_ids": ["aegis/deterministic/exact_match"],
        },
    )
    assert client.experiments.start(experiment.id).status == "running"
    with pytest.raises(ConflictError):
        client.experiments.start(experiment.id)
