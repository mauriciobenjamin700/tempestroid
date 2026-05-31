#!/usr/bin/env python3
"""Bump the project version in pyproject.toml.

Reads the part to bump from the ``PART`` env var (``patch`` | ``minor`` |
``major``; defaults to ``patch``), rewrites the ``version = "X.Y.Z"`` line in
``pyproject.toml`` in place, and prints the transition. Invoked by ``make bump``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def main() -> int:
    """Bump the version and rewrite pyproject.toml.

    Returns:
        Process exit code: 0 on success, 1 on any error.
    """
    part = os.environ.get("PART", "patch")
    if part not in {"patch", "minor", "major"}:
        print(f"ERROR: PART must be patch|minor|major, got {part!r}", file=sys.stderr)
        return 1

    text = PYPROJECT.read_text()
    match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.M)
    if match is None:
        print("ERROR: could not find version in pyproject.toml", file=sys.stderr)
        return 1

    major, minor, patch = (int(g) for g in match.groups())
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1

    old = ".".join(match.groups())
    new = f"{major}.{minor}.{patch}"
    PYPROJECT.write_text(text[: match.start()] + f'version = "{new}"' + text[match.end() :])
    print(f"bumped {old} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
