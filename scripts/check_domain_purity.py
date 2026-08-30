"""Mechanical dependency gate for the domain layer.

Enforces layer 01 (docs/development/layers/01-domain-layer.md): the domain
package may import ONLY the Python standard library and its own submodules.

Usage: python scripts/check_domain_purity.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOMAIN = ROOT / "src" / "aegis" / "domain"

_FORBIDDEN = {
    "pydantic",
    "sqlalchemy",
    "fastapi",
    "starlette",
    "django",
    "celery",
    "redis",
    "httpx",
    "requests",
    "aiohttp",
    "grpc",
    "flask",
    "sqlite3",
    "psycopg",
    "asyncpg",
    "boto3",
    "opentelemetry",
    "numpy",
    "pandas",
}


def _root_of(module: str) -> str:
    return module.split(".", 1)[0]


def check_file(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _root_of(alias.name)
                if root in _FORBIDDEN:
                    errors.append(f"{path}:{node.lineno}: forbidden import '{alias.name}'")
                elif root == "aegis" and not alias.name.startswith("aegis.domain"):
                    errors.append(
                        f"{path}:{node.lineno}: import '{alias.name}' outside the domain layer"
                    )
                elif root not in sys.stdlib_module_names and root != "aegis":
                    errors.append(f"{path}:{node.lineno}: unknown non-stdlib import '{alias.name}'")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".", 1)[0]
            if root in _FORBIDDEN:
                errors.append(f"{path}:{node.lineno}: forbidden import '{node.module}'")
            elif root == "aegis" and not node.module.startswith("aegis.domain"):
                errors.append(
                    f"{path}:{node.lineno}: import '{node.module}' crosses outside the domain layer"
                )
            elif root not in sys.stdlib_module_names and root != "aegis":
                errors.append(f"{path}:{node.lineno}: unknown non-stdlib import '{node.module}'")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(DOMAIN.rglob("*.py")):
        errors.extend(check_file(path))
    if errors:
        for err in errors:
            print(err)
        return 1
    print(f"domain purity OK ({len(list(DOMAIN.rglob('*.py')))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
