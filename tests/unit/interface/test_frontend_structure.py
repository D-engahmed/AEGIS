"""Frontend boundary tests: the dashboard is a separate static deployable.

Per `docs/architecture/container-architecture.md` the dashboard talks only to
the AEGIS REST API and never ships inside the Python package next to the
routing layer. These tests encode that boundary so a regression (embedding the
UI into the API process or hard-coding a same-origin API base) fails the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND = REPO_ROOT / "frontend"
PACKAGE_INTERFACE = REPO_ROOT / "src" / "aegis" / "interface"
PACKAGE_UI = PACKAGE_INTERFACE / "ui"


def _read(*names: str) -> tuple[str, ...]:
    return tuple((FRONTEND / name).read_text(encoding="utf-8") for name in names)


def test_frontend_lives_outside_the_python_package() -> None:
    assert FRONTEND.is_dir()
    assert not PACKAGE_UI.exists(), "ui/ must not sit next to the routing layer"


def test_frontend_is_a_self_contained_static_deployable() -> None:
    names = {p.name for p in FRONTEND.iterdir() if p.is_file()}
    assert {"index.html", "app.js", "styles.css"}.issubset(names)
    assert "config.example.js" in names
    index, app_js, styles = _read("index.html", "app.js", "styles.css")
    assert 'href="styles.css"' in index
    assert 'src="app.js"' in index
    assert "/static/ui" not in index + app_js + styles


def test_app_js_calls_the_api_through_a_configurable_base() -> None:
    (app_js,) = _read("app.js")
    assert "AEGIS_API_BASE" in app_js
    assert re.search(r"const API\s*=\s*String\(window\.AEGIS_API_BASE", app_js)
    assert re.search(r"fetch\(API \+ path", app_js)


def test_app_js_links_api_docs_through_the_configured_base() -> None:
    (app_js,) = _read("app.js")
    assert "${API}/docs" in app_js
    assert 'href="${API}/openapi.json"' in app_js


def test_api_process_does_not_embed_or_serve_the_frontend() -> None:
    app_py = PACKAGE_INTERFACE / "app.py"
    text = app_py.read_text(encoding="utf-8")
    assert "StaticFiles" not in text
    assert "FileResponse" not in text
    assert "/static/ui" not in text
    assert "platform_ui" not in text


def test_package_does_not_bundle_frontend_assets() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "interface/ui" not in pyproject
    pkg_data_segment = pyproject.split("[tool.setuptools.package-data]", 1)
    assert len(pkg_data_segment) == 1, "package-data must not ship frontend files"
