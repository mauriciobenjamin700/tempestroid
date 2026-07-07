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
from typing import cast

__all__ = [
    "AppResolutionError",
    "resolve_app",
    "TempestConfig",
    "read_config",
    "FEATURES",
    "FEATURE_REQUIRES",
    "VISION_FEATURE",
    "resolve_features",
    "UnknownFeatureError",
]

#: The build-time feature flags that gate the heavy optional Android
#: dependencies (each pulls in its own Gradle deps + native code). An app opts
#: in via ``[tool.tempest] features`` or ``tempest build --feature <name>``; the
#: lean default (no features) ships none of them, keeping the APK small.
#:
#: ``vision`` (Trilho G) is the odd one out: besides the native onnxruntime
#: AAR (gated in Gradle like the others), it also needs the Python
#: ``ort_vision_sdk`` staged into the device site-packages — the build sets
#: ``TEMPEST_VISION=1`` when it runs the toolchain so ``02_stage_deps.sh``
#: bundles it. See :data:`VISION_FEATURE`.
FEATURES: tuple[str, ...] = ("camera", "qr", "push", "video", "maps", "vision")

#: The feature whose opt-in also requires staging Python packages
#: (``ort_vision_sdk`` + friends) into the device site-packages, not just a
#: native Gradle dependency. The build translates it to ``TEMPEST_VISION=1``
#: for the toolchain staging step.
VISION_FEATURE: str = "vision"

#: Transitive feature requirements: enabling a key implies its values. ``qr``
#: (ML Kit barcode) runs on the camera preview, so it needs ``camera`` too.
FEATURE_REQUIRES: dict[str, tuple[str, ...]] = {"qr": ("camera",)}


class UnknownFeatureError(ValueError):
    """Raised when a requested feature is not one of :data:`FEATURES`."""


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
        adaptive_icon: Path to an adaptive-icon foreground image
            (``adaptive_icon`` key), or ``None``.
        icon_bg: Adaptive-icon background ``#rrggbb`` (``icon_bg`` key), or ``None``.
        features: The opted-in build features (``features`` key) — the subset of
            :data:`FEATURES` whose heavy native dependencies should be bundled.
            Empty (the default) means the lean build.
    """

    app_id: str | None = None
    app_name: str | None = None
    icon: str | None = None
    splash: str | None = None
    splash_bg: str | None = None
    version: str | None = None
    adaptive_icon: str | None = None
    icon_bg: str | None = None
    features: tuple[str, ...] = ()


def read_config(app_path: str | Path) -> TempestConfig:
    """Read the ``[tool.tempest]`` build config for the project containing ``app``.

    Walks up from the app file to the nearest ``pyproject.toml`` and reads the
    build keys (``id``/``name``/``icon``/``splash``/``splash_bg``/``version``/
    ``adaptive_icon``/``icon_bg``). ``icon``/``splash``/``adaptive_icon`` paths
    are resolved against that pyproject's directory.

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

    def _features() -> tuple[str, ...]:
        value = table.get("features")
        if not isinstance(value, list):
            return ()
        items = cast("list[object]", value)
        return tuple(item for item in items if isinstance(item, str) and item)

    return TempestConfig(
        app_id=_str("id"),
        app_name=_str("name"),
        icon=_path("icon"),
        splash=_path("splash"),
        splash_bg=_str("splash_bg"),
        version=_str("version"),
        adaptive_icon=_path("adaptive_icon"),
        icon_bg=_str("icon_bg"),
        features=_features(),
    )


def resolve_features(requested: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Validate and expand a set of requested build features.

    Validates every name against :data:`FEATURES`, then closes the set over
    :data:`FEATURE_REQUIRES` (so requesting ``qr`` also pulls in ``camera``).
    The result is sorted in :data:`FEATURES` order for a stable, deduplicated
    Gradle property.

    Args:
        requested: The raw feature names from config and/or CLI flags.

    Returns:
        The validated, transitively-closed features in :data:`FEATURES` order.

    Raises:
        UnknownFeatureError: If any requested name is not a known feature.
    """
    wanted = {name.strip().lower() for name in requested if name.strip()}
    unknown = sorted(wanted - set(FEATURES))
    if unknown:
        bad = ", ".join(unknown)
        known = ", ".join(FEATURES)
        raise UnknownFeatureError(
            f"unknown feature(s): {bad}. Known features: {known}."
        )
    for feature in tuple(wanted):
        wanted.update(FEATURE_REQUIRES.get(feature, ()))
    return tuple(name for name in FEATURES if name in wanted)


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
