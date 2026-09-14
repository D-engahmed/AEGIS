"""Mechanical dependency gate for layer boundaries (§4 of the migration plan).

Enforces, per file, the dependency-direction rules that code review alone
cannot hold:

- application/ .... no aegis.execution.*, aegis.infrastructure.*, aegis.interface.*
- interface/routers/ . no aegis.infrastructure.* (no store access), no aegis.execution.*
- infrastructure/ . no aegis.interface.*, no aegis.execution.*
- execution/ ...... no aegis.infrastructure.*, no aegis.interface.*
- aegis_sdk/ ...... no aegis.* at all (dependency-free client)
- infrastructure adapters (classes named *Repository/*Catalog/*Registry/
  *Queue/*Store/*Manager/*Index/*Client) must declare the port they
  implement as an explicit base class, so mypy enforces parity.

Covers module-level AND function-level imports. Relative imports are
resolved to absolute module paths before checking.

Usage: python scripts/check_layer_boundaries.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# package path -> forbidden absolute module prefixes
_FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
    "aegis/application": ("aegis.execution.", "aegis.infrastructure.", "aegis.interface."),
    "aegis/interface/routers": ("aegis.infrastructure.", "aegis.execution."),
    "aegis/infrastructure": ("aegis.interface.", "aegis.execution."),
    "aegis/execution": ("aegis.infrastructure.", "aegis.interface."),
    "aegis_sdk": ("aegis.",),
}

_ADAPTER_SUFFIXES = (
    "Repository",
    "Catalog",
    "Registry",
    "Queue",
    "Store",
    "Manager",
    "Index",
    "Client",
)

# Classes that look like adapters but intentionally declare no port.
_PORT_BASE_ALLOWLIST = frozenset(
    {
        # Aggregate facade over the sub-repositories, not an adapter itself.
        "PostgresStore",
    }
)


def _module_of(path: pathlib.Path) -> str:
    """Dotted module name for a file under src/ (src/aegis/x.py -> aegis.x)."""
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import(module: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    parts = module.split(".")
    base = parts[: len(parts) - node.level] if node.level <= len(parts) else []
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base)


def _iter_absolute_modules(path: pathlib.Path, module: str) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import(module, node)
            if resolved:
                found.append((node.lineno, resolved))
    return found


def _package_key(path: pathlib.Path) -> str | None:
    try:
        relative = path.relative_to(SRC).as_posix()
    except ValueError:
        return None
    for key in _FORBIDDEN_IMPORTS:
        if relative == key or relative.startswith(key + "/"):
            return key
    return None


def check_imports(path: pathlib.Path) -> list[str]:
    key = _package_key(path)
    if key is None:
        return []
    module = _module_of(path)
    errors = []
    for lineno, imported in _iter_absolute_modules(path, module):
        for forbidden in _FORBIDDEN_IMPORTS[key]:
            if imported == forbidden.rstrip(".") or imported.startswith(forbidden):
                errors.append(
                    f"{path}:{lineno}: '{imported}' violates the {key}/ boundary "
                    f"(forbidden: {forbidden}*)"
                )
    return errors


def check_port_bases(path: pathlib.Path) -> list[str]:
    try:
        relative = path.relative_to(SRC / "aegis" / "infrastructure")
    except ValueError:
        return []
    if relative.name == "__init__.py":
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.endswith(_ADAPTER_SUFFIXES):
            continue
        if node.name in _PORT_BASE_ALLOWLIST:
            continue
        if not node.bases:
            errors.append(
                f"{path}:{node.lineno}: adapter '{node.name}' declares no port base "
                "(add the implemented port so mypy enforces parity)"
            )
    return errors


def main() -> int:
    errors: list[str] = []
    files = sorted(SRC.rglob("*.py"))
    for path in files:
        errors.extend(check_imports(path))
        errors.extend(check_port_bases(path))
    if errors:
        for err in errors:
            print(err)
        return 1
    print(f"layer boundaries OK ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
