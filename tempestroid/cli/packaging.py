"""Package and deploy the Android host APK (``tempest build`` / ``tempest run``).

These commands drive the ``android-host/`` Gradle project (the Kotlin/CPython
host from track B) and the Android platform tools (``adb``). They stage the
user's app source as a bundled asset so the built APK boots *that* app instead
of the demo, then shell out to ``gradlew`` and ``adb``.

This needs an Android SDK/NDK and the ``android-host`` tree — i.e. a repo
checkout on a machine with the toolchain, not an installed wheel. Every helper
fails loudly with an actionable message when a prerequisite is missing, so the
desktop path stays honest about what it cannot do here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

__all__ = [
    "ToolchainError",
    "find_android_host",
    "stage_app_source",
    "build_apk",
    "run_on_device",
]

# Asset path inside android-host the host's MainActivity extracts and runs.
_BUNDLED_APP_ASSET = "app/src/main/assets/tempest_app.py"
# Where the global Android SDK lives on the maintainer's WSL host when
# ANDROID_SDK_ROOT is unset (documented in CLAUDE.md / memory).
_SDK_FALLBACK = "/usr/lib/android-sdk"
_HOST_TAG = "tempestroid"


class ToolchainError(RuntimeError):
    """Raised when a build/run prerequisite (host tree, SDK, adb) is missing."""


def find_android_host(start: str | Path | None = None) -> Path:
    """Locate the ``android-host`` Gradle project.

    Honors ``TEMPESTROID_ANDROID_HOST`` first, else walks up from ``start``
    (default: cwd) looking for an ``android-host/gradlew``.

    Args:
        start: Directory to start the upward search from.

    Returns:
        The resolved ``android-host`` directory.

    Raises:
        ToolchainError: If no host project can be found.
    """
    override = os.environ.get("TEMPESTROID_ANDROID_HOST")
    if override:
        host = Path(override).resolve()
        if (host / "gradlew").is_file():
            return host
        raise ToolchainError(
            f"TEMPESTROID_ANDROID_HOST={override} has no gradlew; expected the "
            "android-host project root."
        )
    here = Path(start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / "android-host"
        if (candidate / "gradlew").is_file():
            return candidate
    raise ToolchainError(
        "could not find the android-host project. Run from a tempestroid "
        "checkout, or set TEMPESTROID_ANDROID_HOST to its path."
    )


def _android_env() -> dict[str, str]:
    """Build the subprocess environment with the Android SDK root resolved.

    Returns:
        A copy of ``os.environ`` with ``ANDROID_SDK_ROOT`` set to a usable SDK.

    Raises:
        ToolchainError: If no SDK directory can be located.
    """
    env = dict(os.environ)
    sdk = env.get("ANDROID_SDK_ROOT") or env.get("ANDROID_HOME")
    if not sdk or not Path(sdk).is_dir():
        if Path(_SDK_FALLBACK).is_dir():
            sdk = _SDK_FALLBACK
        else:
            raise ToolchainError(
                "no Android SDK found. Set ANDROID_SDK_ROOT to your SDK path "
                f"(tried ANDROID_SDK_ROOT, ANDROID_HOME, {_SDK_FALLBACK})."
            )
    env["ANDROID_SDK_ROOT"] = sdk
    return env


def stage_app_source(app: str | Path, host: Path) -> Path:
    """Copy the user's app file into the host's bundled-app asset slot.

    Args:
        app: Path to the app's Python file (``make_state`` + ``view``).
        host: The ``android-host`` project root.

    Returns:
        The path of the staged asset.

    Raises:
        FileNotFoundError: If ``app`` does not exist.
    """
    source = Path(app).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"app file not found: {source}")
    asset = host / _BUNDLED_APP_ASSET
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, asset)
    return asset


def _adb() -> str:
    """Resolve the ``adb`` executable.

    Returns:
        The path to ``adb``.

    Raises:
        ToolchainError: If ``adb`` is not on ``PATH``.
    """
    adb = shutil.which("adb")
    if adb is None:
        raise ToolchainError(
            "adb not found on PATH. Install Android platform-tools and ensure "
            "adb is reachable."
        )
    return adb


def build_apk(
    app: str | Path,
    *,
    release: bool = False,
    host: Path | None = None,
) -> Path:
    """Stage the app and build its APK via the host's Gradle wrapper.

    Args:
        app: Path to the app's Python file to bundle.
        release: Build ``assembleRelease`` when ``True``, else ``assembleDebug``.
        host: The ``android-host`` root (auto-located when ``None``).

    Returns:
        The path to the built ``.apk``.

    Raises:
        ToolchainError: If the host tree, SDK, or build output is missing.
        FileNotFoundError: If ``app`` does not exist.
        subprocess.CalledProcessError: If the Gradle build fails.
    """
    host_dir = host or find_android_host()
    stage_app_source(app, host_dir)
    env = _android_env()
    variant = "Release" if release else "Debug"
    # Use the bundled wrapper (8.11.1) — the global Gradle 9.5 is too new for
    # AGP 8.7 (see CLAUDE.md). Run from the host root so ./gradlew resolves.
    cmd = ["./gradlew", f"assemble{variant}"]
    subprocess.run(cmd, cwd=host_dir, env=env, check=True)  # noqa: S603
    apk_dir = host_dir / "app" / "build" / "outputs" / "apk" / variant.lower()
    apks = sorted(apk_dir.glob("*.apk"))
    if not apks:
        raise ToolchainError(f"build succeeded but no APK found in {apk_dir}")
    return apks[0]


def run_on_device(
    app: str | Path,
    *,
    release: bool = False,
    host: Path | None = None,
    stream_logs: bool = True,
) -> int:
    """Build, install on a connected device, launch, and stream logs.

    Args:
        app: Path to the app's Python file to bundle.
        release: Build the release variant when ``True``.
        host: The ``android-host`` root (auto-located when ``None``).
        stream_logs: Tail ``adb logcat`` (filtered to the host tag) after launch.
            Disable in tests.

    Returns:
        The process exit code (``0`` on a clean launch).

    Raises:
        ToolchainError: If a prerequisite is missing.
        subprocess.CalledProcessError: If build/install/launch fails.
    """
    host_dir = host or find_android_host()
    apk = build_apk(app, release=release, host=host_dir)
    env = _android_env()
    adb = _adb()
    subprocess.run([adb, "install", "-r", str(apk)], env=env, check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [adb, "shell", "am", "start", "-n", "org.tempestroid.host/.MainActivity"],
        env=env,
        check=True,
    )
    if not stream_logs:
        return 0
    print(f"streaming logs (tag: {_HOST_TAG}). Ctrl-C to stop.")
    subprocess.run([adb, "logcat", "-v", "tag"], env=env, check=False)  # noqa: S603
    return 0
