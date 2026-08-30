"""Validate the documentation rendering contract.

Checks:
1. Every ``` fence block in docs/*.md is balanced.
2. Every relative markdown link to a *.md/*.markdown target resolves to an
   existing file (external URLs and anchor-only links are ignored).

Usage: python scripts/validate_docs.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)")
_FENCE = "```"


def check_fences(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    count = text.count(_FENCE)
    if count % 2 != 0:
        return [f"{path}: unbalanced ``` fence (odd count {count})"]
    return []


def check_links(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for match in _LINK_RE.finditer(text):
        if match.group(0).startswith("!"):
            continue
        target = match.group(1).split("#", 1)[0].split("?", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#", "/")):
            continue
        if not target.lower().endswith((".md", ".markdown")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"{path}: broken link '{target}'")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(DOCS.rglob("*.md")):
        errors.extend(check_fences(path))
        errors.extend(check_links(path))
    if errors:
        for err in errors:
            print(err)
        return 1
    print(f"docs validation OK ({len(list(DOCS.rglob('*.md')))} markdown files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
