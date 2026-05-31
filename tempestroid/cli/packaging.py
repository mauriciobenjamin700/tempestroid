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
from dataclasses import dataclass
from pathlib import Path

from tempestroid.cli.console import Console, StepError

__all__ = [
    "ToolchainError",
    "PreflightCheck",
    "find_android_host",
    "stage_app_source",
    "connected_devices",
    "preflight",
    "report_preflight",
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


@dataclass(frozen=True)
class PreflightCheck:
    """Outcome of a single environment probe before a build/run.

    Attributes:
        name: Short label for the thing being checked (e.g. ``"adb"``).
        ok: Whether the check passed.
        detail: A resolved value (path, version, device id) or the failure
            reason.
        hint: An actionable suggestion shown when ``ok`` is ``False``.
    """

    name: str
    ok: bool
    detail: str
    hint: str = ""


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


def connected_devices() -> list[str]:
    """List serials of devices in the ``device`` state via ``adb devices``.

    Returns:
        The serials reported as ready, or ``[]`` when adb is missing or no
        device is connected. Never raises — used for diagnostics.
    """
    adb = shutil.which("adb")
    if adb is None:
        return []
    try:
        out = subprocess.run(  # noqa: S603
            [adb, "devices"], check=False, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return []
    serials: list[str] = []
    for line in out.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def preflight(
    *,
    need_device: bool = False,
    host: Path | None = None,
) -> list[PreflightCheck]:
    """Probe the build/run prerequisites without performing the build.

    Checks the ``android-host`` tree, the Android SDK, ``adb`` on ``PATH``, and
    (when ``need_device``) at least one connected device. Each probe yields a
    :class:`PreflightCheck` so the caller can render a transparent report and
    decide whether to proceed.

    Args:
        need_device: Also require a connected device (for ``run``).
        host: A known ``android-host`` root; auto-located when ``None``.

    Returns:
        One :class:`PreflightCheck` per probe, in display order.
    """
    checks: list[PreflightCheck] = []

    try:
        host_dir = host or find_android_host()
        checks.append(PreflightCheck("android-host", True, str(host_dir)))
    except ToolchainError as exc:
        checks.append(
            PreflightCheck(
                "android-host",
                False,
                str(exc),
                "run from a tempestroid checkout or set TEMPESTROID_ANDROID_HOST.",
            )
        )

    try:
        sdk = _android_env()["ANDROID_SDK_ROOT"]
        checks.append(PreflightCheck("android-sdk", True, sdk))
    except ToolchainError as exc:
        checks.append(
            PreflightCheck(
                "android-sdk", False, str(exc), "set ANDROID_SDK_ROOT to your SDK."
            )
        )

    adb = shutil.which("adb")
    if adb is not None:
        checks.append(PreflightCheck("adb", True, adb))
    else:
        checks.append(
            PreflightCheck(
                "adb",
                False,
                "not on PATH",
                "install Android platform-tools and add adb to PATH.",
            )
        )

    if need_device:
        devices = connected_devices()
        if devices:
            checks.append(PreflightCheck("device", True, ", ".join(devices)))
        else:
            checks.append(
                PreflightCheck(
                    "device",
                    False,
                    "no ready device (adb reports none in the device state)",
                    "connect a device, enable USB debugging, run `adb devices`.",
                )
            )

    return checks


def report_preflight(checks: list[PreflightCheck], console: Console) -> bool:
    """Render preflight results as steps and report overall readiness.

    Args:
        checks: The probe results from :func:`preflight`.
        console: The console to render to.

    Returns:
        ``True`` when every check passed, else ``False``.
    """
    ok = True
    for check in checks:
        if check.ok:
            console.info(f"{check.name}: {check.detail}")
        else:
            ok = False
            console.fail(f"{check.name}: {check.detail}")
            if check.hint:
                console.info(f"  → {check.hint}")
    return ok


def build_apk(
    app: str | Path,
    *,
    release: bool = False,
    host: Path | None = None,
    console: Console | None = None,
    run_preflight: bool = True,
) -> Path:
    """Stage the app and build its APK via the host's Gradle wrapper.

    Args:
        app: Path to the app's Python file to bundle.
        release: Build ``assembleRelease`` when ``True``, else ``assembleDebug``.
        host: The ``android-host`` root (auto-located when ``None``).
        console: Step reporter for transparent output (a quiet one when ``None``).
        run_preflight: Run the prerequisite probe first. Set ``False`` when the
            caller (e.g. :func:`run_on_device`) already ran it.

    Returns:
        The path to the built ``.apk``.

    Raises:
        ToolchainError: If the host tree, SDK, or build output is missing.
        FileNotFoundError: If ``app`` does not exist.
        subprocess.CalledProcessError: If the Gradle build fails.
    """
    con = console or Console()
    variant = "Release" if release else "Debug"

    if run_preflight:
        with con.step("Preflight (host tree, SDK, adb)"):
            if not report_preflight(preflight(host=host), con):
                raise StepError("missing prerequisite")

    host_dir = host or find_android_host()
    env = _android_env()

    with con.step(f"Staging app source ({Path(app).name})"):
        asset = stage_app_source(app, host_dir)
        con.detail(f"copied to {asset}")

    with con.step(f"Gradle assemble{variant}"):
        # Use the bundled wrapper (8.11.1) — the global Gradle 9.5 is too new
        # for AGP 8.7 (see CLAUDE.md). Run from the host root so ./gradlew
        # resolves.
        con.run_command(
            ["./gradlew", f"assemble{variant}"], cwd=host_dir, env=env
        )

    apk_dir = host_dir / "app" / "build" / "outputs" / "apk" / variant.lower()
    apks = sorted(apk_dir.glob("*.apk"))
    if not apks:
        raise ToolchainError(f"build succeeded but no APK found in {apk_dir}")
    con.info(f"APK: {apks[0]}")
    return apks[0]


def run_on_device(
    app: str | Path,
    *,
    release: bool = False,
    host: Path | None = None,
    stream_logs: bool = True,
    console: Console | None = None,
) -> int:
    """Build, install on a connected device, launch, and stream logs.

    Args:
        app: Path to the app's Python file to bundle.
        release: Build the release variant when ``True``.
        host: The ``android-host`` root (auto-located when ``None``).
        stream_logs: Tail ``adb logcat`` (filtered to the host tag) after launch.
            Disable in tests.
        console: Step reporter for transparent output (a quiet one when ``None``).

    Returns:
        The process exit code (``0`` on a clean launch).

    Raises:
        ToolchainError: If a prerequisite is missing.
        subprocess.CalledProcessError: If build/install/launch fails.
    """
    con = console or Console()

    with con.step("Preflight (host tree, SDK, adb, device)"):
        if not report_preflight(preflight(need_device=True, host=host), con):
            raise StepError("missing prerequisite")

    host_dir = host or find_android_host()
    apk = build_apk(
        app, release=release, host=host_dir, console=con, run_preflight=False
    )
    env = _android_env()
    adb = _adb()

    with con.step(f"Installing APK ({apk.name})"):
        con.run_command([adb, "install", "-r", str(apk)], env=env)

    with con.step("Launching org.tempestroid.host/.MainActivity"):
        con.run_command(
            [adb, "shell", "am", "start", "-n", "org.tempestroid.host/.MainActivity"],
            env=env,
        )

    if not stream_logs:
        return 0
    con.info(f"streaming logs (tag: {_HOST_TAG}). Ctrl-C to stop.")
    subprocess.run([adb, "logcat", "-v", "tag"], env=env, check=False)  # noqa: S603
    return 0
