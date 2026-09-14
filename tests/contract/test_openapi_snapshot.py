"""OpenAPI snapshot: any wire change must be reviewed, never accidental.

The checked-in ``snapshots/openapi.json`` is the reviewed contract. If this
test fails, either the change is unintended (fix the code) or it is a
deliberate contract change (regenerate the snapshot and review the diff)::

    python -c "import json; from aegis.interface.app import create_app;
    from aegis.interface.container import Container;
    json.dump(create_app(Container()).openapi(),
    open('tests/contract/snapshots/openapi.json','w'), indent=2, sort_keys=True)"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis.interface.app import create_app
from aegis.interface.container import Container

pytestmark = pytest.mark.contract

SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi.json"


def _current_schema() -> dict:
    return create_app(Container()).openapi()


def test_openapi_snapshot_matches() -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(_current_schema(), sort_keys=True))
    assert actual == expected, (
        "OpenAPI schema drifted from the reviewed snapshot. "
        "If deliberate, regenerate tests/contract/snapshots/openapi.json "
        "and review the diff; otherwise fix the code."
    )


def test_every_route_has_a_stable_operation_id() -> None:
    schema = _current_schema()
    missing = [
        path
        for path, item in schema["paths"].items()
        for method, op in item.items()
        if method in {"get", "post", "put", "patch", "delete"} and not op.get("operationId")
    ]
    assert missing == [], f"routes without operationId: {missing}"
