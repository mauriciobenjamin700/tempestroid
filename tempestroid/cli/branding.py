"""Per-app branding for ``tempest build``: launcher icon + boot splash.

The host ships defaults (a tempestroid launcher icon and an asset-drawn boot
splash that covers the CPython boot — see ``android-host``). This module lets a
build override them per app:

* **icon** (``--icon``) — a PNG written over the host's ``res/mipmap-*`` launcher
  icon. Only the **Gradle** build can do this (the launcher icon is a *compiled*
  resource; an APK repackage can't rewrite ``resources.arsc``), so ``--fast``
  reports it as unsupported and keeps the default icon.
* **splash** (``--splash``) + **splash bg** (``--splash-bg``) — the splash image
  and background colour. These live as **assets** at stable paths
  (``assets/tempest/splash.png`` / ``assets/tempest/splash_bg.txt``), so **both**
  the Gradle build (staged into the host source) and the ``--fast`` repackage
  (zip-entry replacement) can override them.

The asset paths here MUST match the host contract in ``android-host`` (the
``MainActivity`` reads exactly these).
"""

from __future__ import annotations

import contextlib
import re
import shutil
import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Branding",
    "SPLASH_ASSET",
    "SPLASH_BG_ASSET",
    "load_branding",
    "staged_into_host",
    "apk_asset_replacements",
]

#: Splash asset paths inside the APK / host source (the host's MainActivity reads
#: exactly these — keep in sync with ``android-host``).
SPLASH_ASSET = "assets/tempest/splash.png"
SPLASH_BG_ASSET = "assets/tempest/splash_bg.txt"

#: The adaptive-icon foreground drawable path (relative to ``res/``). The manifest
#: keeps ``@mipmap/ic_launcher``; the ``anydpi-v26`` XML below redirects it to an
#: adaptive icon referencing this foreground + the background colour, so API 26+
#: launchers apply their mask (rounded/squircle) and older ones keep the PNG.
_FG_DRAWABLE = "drawable/ic_launcher_foreground.png"
_BG_COLOR_RES = "values/ic_launcher_background.xml"
_ADAPTIVE_XML = "mipmap-anydpi-v26/ic_launcher.xml"
_ADAPTIVE_XML_ROUND = "mipmap-anydpi-v26/ic_launcher_round.xml"

_ADAPTIVE_ICON_XML = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
    '    <background android:drawable="@color/ic_launcher_background" />\n'
    '    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n'
    "</adaptive-icon>\n"
)

_DEFAULT_ICON_BG = "#FFFFFF"

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _bg_color_xml(color: str) -> str:
    """Render the ``ic_launcher_background`` colour resource XML.

    Args:
        color: A ``#rrggbb`` colour string.

    Returns:
        The ``values/ic_launcher_background.xml`` document text.
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        f'    <color name="ic_launcher_background">{color}</color>\n'
        "</resources>\n"
    )


@dataclass(frozen=True)
class Branding:
    """Per-app branding overrides for a build.

    Attributes:
        icon: A launcher-icon PNG (Gradle only), or ``None`` to keep the default.
        splash: A splash-image PNG, or ``None`` to keep the default.
        splash_bg: A ``#rrggbb`` splash background, or ``None`` to keep the default.
        adaptive_icon: An adaptive-icon **foreground** PNG (Gradle only), or
            ``None``. When set, the build emits a real Android adaptive icon so
            the launcher applies its mask (rounded/squircle) — see
            :func:`staged_into_host`.
        icon_bg: The adaptive-icon **background** ``#rrggbb`` colour, or ``None``
            (defaults to ``#FFFFFF`` when an ``adaptive_icon`` is set without one).
    """

    icon: Path | None = None
    splash: Path | None = None
    splash_bg: str | None = None
    adaptive_icon: Path | None = None
    icon_bg: str | None = None

    def is_empty(self) -> bool:
        """Report whether no branding override is set.

        Returns:
            ``True`` when every branding field is unset.
        """
        return (
            self.icon is None
            and self.splash is None
            and self.splash_bg is None
            and self.adaptive_icon is None
            and self.icon_bg is None
        )


def load_branding(
    icon: str | None,
    splash: str | None,
    splash_bg: str | None,
    adaptive_icon: str | None = None,
    icon_bg: str | None = None,
) -> Branding:
    """Validate the branding CLI inputs into a :class:`Branding`.

    Args:
        icon: Path to a launcher-icon PNG, or ``None``.
        splash: Path to a splash-image PNG, or ``None``.
        splash_bg: A ``#rrggbb`` colour string, or ``None``.
        adaptive_icon: Path to an adaptive-icon foreground PNG, or ``None``.
        icon_bg: A ``#rrggbb`` adaptive-icon background colour, or ``None``.

    Returns:
        The validated branding.

    Raises:
        ValueError: If a given path is missing/not a PNG, or a colour is not
            ``#rrggbb``.
    """
    icon_path = _check_png(icon, "--icon") if icon else None
    splash_path = _check_png(splash, "--splash") if splash else None
    adaptive_path = (
        _check_png(adaptive_icon, "--adaptive-icon") if adaptive_icon else None
    )
    if splash_bg is not None and not _HEX_RE.match(splash_bg):
        raise ValueError(f"--splash-bg must be #rrggbb, got {splash_bg!r}")
    if icon_bg is not None and not _HEX_RE.match(icon_bg):
        raise ValueError(f"--icon-bg must be #rrggbb, got {icon_bg!r}")
    return Branding(
        icon=icon_path,
        splash=splash_path,
        splash_bg=splash_bg,
        adaptive_icon=adaptive_path,
        icon_bg=icon_bg,
    )


def _check_png(path: str, flag: str) -> Path:
    """Resolve a PNG path argument, validating it exists and is a ``.png``.

    Args:
        path: The path string.
        flag: The CLI flag name (for the error message).

    Returns:
        The resolved path.

    Raises:
        ValueError: If the file is missing or not a ``.png``.
    """
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise ValueError(f"{flag}: file not found: {resolved}")
    if resolved.suffix.lower() != ".png":
        raise ValueError(f"{flag}: must be a .png file, got {resolved.name}")
    return resolved


@contextlib.contextmanager
def staged_into_host(host: Path, branding: Branding) -> Generator[None, None, None]:
    """Overlay the branding onto the host source for a Gradle build, then restore.

    Backs up every host file it overwrites (and tracks every file/dir it newly
    creates) and restores them on exit, so the build leaves the (possibly
    checked-in) ``android-host`` source untouched:

    * ``icon`` → every ``res/mipmap-*/ic_launcher.png`` and ``ic_launcher_round.png``.
    * ``splash`` → ``app/src/main/assets/tempest/splash.png``.
    * ``splash_bg`` → ``app/src/main/assets/tempest/splash_bg.txt``.
    * ``adaptive_icon`` (+ ``icon_bg``) → an Android **adaptive icon**:
      ``res/drawable/ic_launcher_foreground.png`` (the foreground),
      ``res/values/ic_launcher_background.xml`` (the background colour), and
      ``res/mipmap-anydpi-v26/ic_launcher{,_round}.xml`` (the adaptive-icon XML
      that redirects ``@mipmap/ic_launcher`` to them on API 26+). The launcher
      then masks the icon (rounded/squircle) like a native app.

    Args:
        host: The ``android-host`` Gradle project directory.
        branding: The branding overrides (a no-op when empty).

    Yields:
        None. The host source carries the overrides for the duration.
    """
    if branding.is_empty():
        yield
        return

    res = host / "app" / "src" / "main" / "res"
    assets = host / "app" / "src" / "main" / "assets" / "tempest"
    targets: list[Path] = []
    if branding.icon is not None:
        targets.extend(sorted(res.glob("mipmap-*/ic_launcher.png")))
        targets.extend(sorted(res.glob("mipmap-*/ic_launcher_round.png")))
    if branding.splash is not None:
        targets.append(assets / "splash.png")
    if branding.splash_bg is not None:
        targets.append(assets / "splash_bg.txt")

    # Back up overwritten files OUTSIDE the source tree — a stray ``.bak`` left
    # inside ``res/`` makes AGP's resource compiler fail ("file name must end
    # with .xml or .png").
    backup_dir = Path(tempfile.mkdtemp(prefix="tempest-branding-"))
    backups: list[tuple[Path, Path]] = []
    # Files/dirs newly created by adaptive staging — removed on restore so the
    # host tree is left exactly as found (these paths don't ship in the host).
    created_files: list[Path] = []
    created_dirs: list[Path] = []

    def _stage_write(target: Path, *, data: bytes) -> None:
        """Write ``data`` to ``target``, backing up or tracking it for restore."""
        if target.exists():
            backup = backup_dir / f"{len(backups)}_{target.name}"
            shutil.copy2(target, backup)
            backups.append((target, backup))
        else:
            for parent in reversed(target.parents):
                if parent.is_relative_to(res) and not parent.exists():
                    parent.mkdir(parents=True, exist_ok=True)
                    created_dirs.append(parent)
            created_files.append(target)
        target.write_bytes(data)

    try:
        for index, target in enumerate(targets):
            if target.exists():
                backup = backup_dir / f"bak{index}_{target.name}"
                shutil.copy2(target, backup)
                backups.append((target, backup))
        if branding.icon is not None:
            for target in sorted(res.glob("mipmap-*/ic_launcher.png")):
                shutil.copyfile(branding.icon, target)
            for target in sorted(res.glob("mipmap-*/ic_launcher_round.png")):
                shutil.copyfile(branding.icon, target)
        if branding.splash is not None:
            (assets).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(branding.splash, assets / "splash.png")
        if branding.splash_bg is not None:
            (assets).mkdir(parents=True, exist_ok=True)
            (assets / "splash_bg.txt").write_text(
                branding.splash_bg + "\n", encoding="utf-8"
            )
        if branding.adaptive_icon is not None:
            color = branding.icon_bg or _DEFAULT_ICON_BG
            _stage_write(
                res / _FG_DRAWABLE, data=branding.adaptive_icon.read_bytes()
            )
            _stage_write(
                res / _BG_COLOR_RES, data=_bg_color_xml(color).encode("utf-8")
            )
            xml = _ADAPTIVE_ICON_XML.encode("utf-8")
            _stage_write(res / _ADAPTIVE_XML, data=xml)
            _stage_write(res / _ADAPTIVE_XML_ROUND, data=xml)
        yield
    finally:
        for target, backup in backups:
            shutil.copy2(backup, target)
        for created in created_files:
            created.unlink(missing_ok=True)
        # Deepest-first so a parent is only removed after its children.
        for directory in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        shutil.rmtree(backup_dir, ignore_errors=True)


def apk_asset_replacements(branding: Branding) -> dict[str, bytes]:
    """Build the APK asset-entry replacements for the ``--fast`` repackage path.

    Only the splash assets can be swapped this way (stable, uncompiled asset
    paths); the launcher icon is a compiled resource and is left to the Gradle
    build.

    Args:
        branding: The branding overrides.

    Returns:
        A mapping of APK zip-entry path → replacement bytes (empty when no splash
        override is set).
    """
    replacements: dict[str, bytes] = {}
    if branding.splash is not None:
        replacements[SPLASH_ASSET] = branding.splash.read_bytes()
    if branding.splash_bg is not None:
        replacements[SPLASH_BG_ASSET] = (branding.splash_bg + "\n").encode("utf-8")
    return replacements
