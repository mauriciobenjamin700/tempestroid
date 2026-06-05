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

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Branding:
    """Per-app branding overrides for a build.

    Attributes:
        icon: A launcher-icon PNG (Gradle only), or ``None`` to keep the default.
        splash: A splash-image PNG, or ``None`` to keep the default.
        splash_bg: A ``#rrggbb`` splash background, or ``None`` to keep the default.
    """

    icon: Path | None = None
    splash: Path | None = None
    splash_bg: str | None = None

    def is_empty(self) -> bool:
        """Report whether no branding override is set.

        Returns:
            ``True`` when icon, splash and splash_bg are all unset.
        """
        return self.icon is None and self.splash is None and self.splash_bg is None


def load_branding(
    icon: str | None, splash: str | None, splash_bg: str | None
) -> Branding:
    """Validate the branding CLI inputs into a :class:`Branding`.

    Args:
        icon: Path to a launcher-icon PNG, or ``None``.
        splash: Path to a splash-image PNG, or ``None``.
        splash_bg: A ``#rrggbb`` colour string, or ``None``.

    Returns:
        The validated branding.

    Raises:
        ValueError: If a given path is missing/not a PNG, or the colour is not
            ``#rrggbb``.
    """
    icon_path = _check_png(icon, "--icon") if icon else None
    splash_path = _check_png(splash, "--splash") if splash else None
    if splash_bg is not None and not _HEX_RE.match(splash_bg):
        raise ValueError(f"--splash-bg must be #rrggbb, got {splash_bg!r}")
    return Branding(icon=icon_path, splash=splash_path, splash_bg=splash_bg)


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

    Backs up every host file it overwrites and restores it on exit, so the build
    leaves the (possibly checked-in) ``android-host`` source untouched:

    * ``icon`` → every ``res/mipmap-*/ic_launcher.png`` and ``ic_launcher_round.png``.
    * ``splash`` → ``app/src/main/assets/tempest/splash.png``.
    * ``splash_bg`` → ``app/src/main/assets/tempest/splash_bg.txt``.

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
    try:
        for index, target in enumerate(targets):
            if target.exists():
                backup = backup_dir / f"{index}_{target.name}"
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
        yield
    finally:
        for target, backup in backups:
            shutil.copy2(backup, target)
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
