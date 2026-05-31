"""Resolve the target app file for ``tempest`` commands.

Commands that act on an app (``dev``/``serve``/``build``/``run``) accept the app
path as an optional argument. When omitted, the path is read from
``[tool.tempest] app`` in the nearest ``pyproject.toml`` (walking up from the
current directory), so inside a scaffolded project you can run ``tempest dev``
with no arguments.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

__all__ = ["AppResolutionError", "resolve_app"]


class AppResolutionError(RuntimeError):
    """Raised when no app path is given and none can be inferred from config."""


def _read_configured_app(start: Path) -> Path | None:
    """Find ``[tool.tempest] app`` in the nearest ``pyproject.toml``.

    Walks up from ``start`` looking for a ``pyproject.toml`` whose
    ``[tool.tempest]`` table names an ``app``; returns it resolved against that
    file's directory.

    Args:
        start: Directory to begin the upward search from.

    Returns:
        The resolved app path, or ``None`` if no config declares one.
    """
    for directory in (start, *start.parents):
        config = directory / "pyproject.toml"
        if not config.is_file():
            continue
        try:
            data = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return None
        app = data.get("tool", {}).get("tempest", {}).get("app")
        if isinstance(app, str) and app:
            return (directory / app).resolve()
        # A pyproject without [tool.tempest] still ends the search: it marks the
        # project root, and walking further would pick an unrelated parent.
        return None
    return None


def resolve_app(app_path: str | None, *, start: str | Path | None = None) -> str:
    """Resolve the app file path from an explicit argument or project config.

    Args:
        app_path: An explicit path passed on the command line, or ``None``.
        start: Directory to search for ``pyproject.toml`` (default: cwd).

    Returns:
        The resolved app file path as a string.

    Raises:
        AppResolutionError: If ``app_path`` is ``None`` and no
            ``[tool.tempest] app`` can be found.
    """
    if app_path:
        return app_path
    configured = _read_configured_app(Path(start or Path.cwd()).resolve())
    if configured is not None:
        return str(configured)
    raise AppResolutionError(
        "no app file given and none configured. Pass a path (e.g. "
        "`tempest dev app.py`) or run inside a project with `[tool.tempest] app` "
        "in pyproject.toml (scaffold one with `tempest new .`)."
    )
