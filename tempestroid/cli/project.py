"""Resolve the target app file for ``tempest`` commands.

Commands that act on an app (``dev``/``serve``/``build``/``run``) accept the app
path as an optional argument. When omitted, the path is read from
``[tool.tempest] app`` in the nearest ``pyproject.toml`` (walking up from the
current directory), so inside a scaffolded project you can run ``tempest dev``
with no arguments.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["AppResolutionError", "resolve_app", "TempestConfig", "read_config"]


class AppResolutionError(RuntimeError):
    """Raised when no app path is given and none can be inferred from config."""


@dataclass(frozen=True)
class TempestConfig:
    """The ``[tool.tempest]`` build config resolved from a project's pyproject.

    Every field is optional; the build derives sensible defaults (from the
    project name) when a value is absent. ``icon``/``splash`` are resolved to
    absolute paths against the project directory.

    Attributes:
        app_id: The ``applicationId`` (``id`` key), or ``None`` to derive one.
        app_name: The launcher label (``name`` key), or ``None`` to derive one.
        icon: Path to a launcher-icon image (``icon`` key), or ``None``.
        splash: Path to a boot-splash image (``splash`` key), or ``None``.
        splash_bg: Splash background ``#rrggbb`` (``splash_bg`` key), or ``None``.
        version: The versionName (``version`` key), or ``None`` (default 1.0.0).
    """

    app_id: str | None = None
    app_name: str | None = None
    icon: str | None = None
    splash: str | None = None
    splash_bg: str | None = None
    version: str | None = None


def read_config(app_path: str | Path) -> TempestConfig:
    """Read the ``[tool.tempest]`` build config for the project containing ``app``.

    Walks up from the app file to the nearest ``pyproject.toml`` and reads the
    build keys (``id``/``name``/``icon``/``splash``/``splash_bg``/``version``).
    ``icon``/``splash`` paths are resolved against that pyproject's directory.

    Args:
        app_path: Path to the app's entry file.

    Returns:
        The resolved :class:`TempestConfig` (all-``None`` when no config found).
    """
    start = Path(app_path).resolve().parent
    found: tuple[Path, dict[str, object]] | None = None
    for directory in (start, *start.parents):
        config = directory / "pyproject.toml"
        if not config.is_file():
            continue
        try:
            data = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return TempestConfig()
        found = (directory, data.get("tool", {}).get("tempest", {}))
        break
    if found is None:
        return TempestConfig()
    directory, table = found

    def _str(key: str) -> str | None:
        value = table.get(key)
        return value if isinstance(value, str) and value else None

    def _path(key: str) -> str | None:
        value = _str(key)
        return str((directory / value).resolve()) if value else None

    return TempestConfig(
        app_id=_str("id"),
        app_name=_str("name"),
        icon=_path("icon"),
        splash=_path("splash"),
        splash_bg=_str("splash_bg"),
        version=_str("version"),
    )


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
