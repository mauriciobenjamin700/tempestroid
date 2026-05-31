"""APK packaging + device run (phase C: ``tempest build`` / ``tempest run``).

``build`` embeds an app's source into the Android host as an asset and invokes
the host's Gradle build to produce an APK. ``run`` additionally installs it on a
connected device and streams logs.

The Android host (Gradle/Kotlin/C scaffold) is not shipped inside the Python
package, so its location is resolved from ``TEMPEST_ANDROID_HOST`` or, failing
that, the ``android-host/`` directory at the repo root (development checkout).
Both commands need the Android SDK/NDK + a JDK; ``run`` also needs ``adb`` and a
connected device.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

__all__ = ["run_build", "run_run", "android_host_dir"]


def android_host_dir() -> Path:
    """Resolve the Android host scaffold directory.

    Returns:
        The ``android-host`` directory.

    Raises:
        FileNotFoundError: If it cannot be located.
    """
    override = os.environ.get("TEMPEST_ANDROID_HOST")
    candidates = [
        Path(override) if override else None,
        # repo checkout: src/tempestroid/cli/packaging.py → repo root
        Path(__file__).resolve().parents[3] / "android-host",
        Path.cwd() / "android-host",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "gradlew").exists():
            return candidate
    raise FileNotFoundError(
        "android-host not found; set TEMPEST_ANDROID_HOST to the host scaffold "
        "(the directory containing gradlew)."
    )


def _embed_app(host: Path, app: str | Path) -> None:
    """Copy the app source into the host's assets as ``tempest_app.py``.

    Args:
        host: The android-host directory.
        app: Path to the app file to embed.

    Raises:
        FileNotFoundError: If the app file does not exist.
    """
    app_file = Path(app).resolve()
    if not app_file.is_file():
        raise FileNotFoundError(f"app file not found: {app_file}")
    assets = host / "app" / "src" / "main" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(app_file, assets / "tempest_app.py")


def _gradle_assemble(host: Path, *, release: bool) -> Path:
    """Run the host's Gradle assemble task and return the built APK.

    Args:
        host: The android-host directory.
        release: Build the release variant instead of debug.

    Returns:
        Path to the built APK.

    Raises:
        subprocess.CalledProcessError: If the Gradle build fails.
        FileNotFoundError: If no APK is produced.
    """
    variant = "Release" if release else "Debug"
    subprocess.run(
        ["./gradlew", f":app:assemble{variant}", "--console=plain"],
        cwd=host,
        check=True,
    )
    out_dir = host / "app" / "build" / "outputs" / "apk" / variant.lower()
    apks = sorted(out_dir.glob("*.apk"))
    if not apks:
        raise FileNotFoundError(f"no APK produced in {out_dir}")
    return apks[0]


def run_build(app: str, *, release: bool = False) -> int:
    """Embed ``app`` and build an APK; copy it to ``./dist``.

    Args:
        app: Path to the app file to embed.
        release: Build the release variant.

    Returns:
        The process exit code.
    """
    try:
        host = android_host_dir()
        _embed_app(host, app)
        apk = _gradle_assemble(host, release=release)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"build failed: {exc}")
        return 1
    dist = Path.cwd() / "dist"
    dist.mkdir(exist_ok=True)
    target = dist / apk.name
    shutil.copyfile(apk, target)
    print(f"built {target}")
    return 0


def run_run(app: str) -> int:
    """Build a debug APK, install it, launch it, and stream logs.

    Args:
        app: Path to the app file to run.

    Returns:
        The process exit code.
    """
    try:
        host = android_host_dir()
        _embed_app(host, app)
        apk = _gradle_assemble(host, release=False)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"build failed: {exc}")
        return 1

    pkg = "org.tempestroid.host"
    try:
        subprocess.run(["adb", "install", "-r", str(apk)], check=True)
        subprocess.run(["adb", "shell", "am", "force-stop", pkg], check=True)
        subprocess.run(
            ["adb", "shell", "am", "start", "-n", f"{pkg}/.MainActivity"], check=True
        )
        subprocess.run(["adb", "logcat", "-c"], check=True)
        print("streaming logs (Ctrl-C to stop)…")
        subprocess.run(
            ["adb", "logcat", "-s", "tempestroid:*", "python.stdout:*",
             "python.stderr:*"],
            check=False,
        )
    except FileNotFoundError:
        print("adb not found on PATH; install the Android platform-tools.")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"run failed: {exc}")
        return 1
    return 0
