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
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tempestroid.cli.console import Console, StepError

__all__ = [
    "ToolchainError",
    "PreflightCheck",
    "find_android_host",
    "stage_app_source",
    "stage_app_bundle",
    "connected_devices",
    "preflight",
    "report_preflight",
    "build_apk",
    "run_on_device",
    "host_apk_url",
    "bundled_host_apk",
    "resolve_host_apk",
    "install_host",
    "host_installed",
    "deploy_offline",
    "adb_reverse",
    "launch_host_dev",
]

# Asset path inside android-host the host's MainActivity extracts and runs.
_BUNDLED_APP_ASSET = "app/src/main/assets/tempest_app.py"
# Multi-file project bundle the host extracts onto sys.path and runs (the entry
# is recorded in the bundle's manifest). Supersedes the single-file asset above.
_BUNDLED_APP_BUNDLE = "app/src/main/assets/tempest_app_bundle.zip"
# Where the global Android SDK lives on the maintainer's WSL host when
# ANDROID_SDK_ROOT is unset (documented in CLAUDE.md / memory).
_SDK_FALLBACK = "/usr/lib/android-sdk"
_HOST_TAG = "tempestroid"
# The prebuilt host: application id, launch activity, and the dev-mode intent
# extra MainActivity reads to point its code-push client at a dev server.
_HOST_PACKAGE = "org.tempestroid.host"
_HOST_ACTIVITY = f"{_HOST_PACKAGE}/.MainActivity"
_DEV_URL_EXTRA = "tempest_dev_url"
# GitHub repo that publishes the prebuilt host APK as a release asset.
_HOST_REPO = "mauriciobenjamin700/tempestroid"


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
        "could not find the android-host project (needed only to BUILD an APK "
        "from source). For a device run you usually don't need it: install the "
        "prebuilt host once with `tempest install`, then push your app with "
        "`tempest serve <app.py>` — no Android SDK/NDK required. To build from "
        "source instead, run from a tempestroid checkout or set "
        "TEMPESTROID_ANDROID_HOST to its path."
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


def stage_app_bundle(app: str | Path, host: Path) -> Path:
    """Bundle the app's whole project tree into the host's bundled-app slot.

    Resolves the project root + entry from ``app`` (see
    :func:`tempestroid.cli.bundle.resolve_project`), zips the importable tree,
    and writes it to the host's ``tempest_app_bundle.zip`` asset so the built
    APK boots *that* multi-file project standalone (no dev server). Removes any
    stale legacy single-file ``tempest_app.py`` asset so the host doesn't pick
    it up instead of the bundle.

    Args:
        app: Path to the app's entry Python file.
        host: The ``android-host`` project root.

    Returns:
        The path of the staged bundle asset.

    Raises:
        FileNotFoundError: If ``app`` does not exist.
    """
    from tempestroid.cli.bundle import build_bundle, resolve_project

    layout = resolve_project(app)
    asset = host / _BUNDLED_APP_BUNDLE
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(build_bundle(layout))
    legacy = host / _BUNDLED_APP_ASSET
    legacy.unlink(missing_ok=True)
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
                "for a device run use `tempest install` + `tempest serve` "
                "(no source build); to build an APK, run from a checkout or set "
                "TEMPESTROID_ANDROID_HOST.",
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

    with con.step(f"Bundling project ({Path(app).name})"):
        asset = stage_app_bundle(app, host_dir)
        con.detail(f"bundled to {asset} ({asset.stat().st_size} bytes)")

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

    with con.step(f"Launching {_HOST_ACTIVITY}"):
        con.run_command(
            [adb, "shell", "am", "start", "-n", _HOST_ACTIVITY],
            env=env,
        )

    if not stream_logs:
        return 0
    con.info(f"streaming logs (tag: {_HOST_TAG}). Ctrl-C to stop.")
    subprocess.run([adb, "logcat", "-v", "tag"], env=env, check=False)  # noqa: S603
    return 0


def host_apk_url(version: str) -> str:
    """Build the download URL for the prebuilt host APK of a given version.

    Honors ``TEMPESTROID_HOST_APK_URL`` as a full override; otherwise points at
    the GitHub release asset for the ``v<version>`` tag.

    Args:
        version: The tempestroid version whose host APK to fetch.

    Returns:
        The ``http(s)`` URL of the host APK.
    """
    override = os.environ.get("TEMPESTROID_HOST_APK_URL")
    if override:
        return override
    return (
        f"https://github.com/{_HOST_REPO}/releases/download/"
        f"v{version}/tempest-host-{version}.apk"
    )


def _host_apk_cache_dir() -> Path:
    """Resolve (and create) the cache directory for downloaded host APKs.

    Returns:
        ``$XDG_CACHE_HOME/tempestroid`` (or ``~/.cache/tempestroid``).
    """
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    cache = Path(base) / "tempestroid"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def bundled_host_apk() -> Path | None:
    """Locate the prebuilt host APK shipped inside the installed package.

    The wheel bundles ``tempestroid/_assets/host.apk`` (see ``pyproject.toml``
    ``[tool.hatch.build] artifacts``), so ``tempest install`` works offline with
    no download. Returns ``None`` when the asset is absent (e.g. an editable
    checkout where the APK hasn't been staged via ``make stage-host``).

    Returns:
        The filesystem path to the bundled APK, or ``None`` if not present.
    """
    from importlib import resources

    try:
        resource = resources.files("tempestroid").joinpath("_assets", "host.apk")
    except (ModuleNotFoundError, AttributeError):
        return None
    # Wheels install unzipped, so the traversable is a real filesystem path.
    if resource.is_file():
        return Path(str(resource))
    return None


def resolve_host_apk(
    source: str | None,
    *,
    version: str,
    console: Console | None = None,
) -> Path:
    """Resolve a host APK to a local file: bundled, a path, a URL, or a release.

    Resolution order: an explicit ``source`` (a local ``.apk`` path used as-is,
    an ``http(s)`` URL downloaded); else ``TEMPESTROID_HOST_APK`` (a local path);
    else the **bundled** asset shipped in the wheel (offline, the normal case);
    else a cached/fresh download of the default release APK for ``version``
    (overridable via ``TEMPESTROID_HOST_APK_URL``). Downloads are cached under the
    user cache dir and reused on subsequent calls.

    Args:
        source: A local ``.apk`` path or ``http(s)`` URL, or ``None`` to use the
            environment / bundled asset / default release.
        version: The tempestroid version for the default release URL.
        console: Optional step reporter for download progress.

    Returns:
        The local path of the resolved ``.apk``.

    Raises:
        ToolchainError: If a local path is missing or the download fails.
    """
    con = console or Console()
    if source is None:
        source = os.environ.get("TEMPESTROID_HOST_APK")
    if source is not None and not source.startswith(("http://", "https://")):
        path = Path(source).expanduser().resolve()
        if not path.is_file():
            raise ToolchainError(f"host APK not found: {path}")
        return path

    if source is None:
        bundled = bundled_host_apk()
        if bundled is not None:
            con.info(f"using bundled host APK: {bundled}")
            return bundled

    url = source or host_apk_url(version)
    dest = _host_apk_cache_dir() / f"tempest-host-{version}.apk"
    if dest.is_file():
        con.info(f"using cached host APK: {dest}")
        return dest
    with con.step(f"Downloading host APK ({url})"):
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 - http(s) guarded above
        except urllib.error.HTTPError as exc:
            dest.unlink(missing_ok=True)
            raise ToolchainError(
                f"could not download host APK from {url} (HTTP {exc.code}). "
                "Publish a host APK to that release, pass a local .apk path, or "
                "set TEMPESTROID_HOST_APK / TEMPESTROID_HOST_APK_URL."
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            dest.unlink(missing_ok=True)
            raise ToolchainError(
                f"could not download host APK from {url}: {exc}"
            ) from exc
    con.detail(f"saved to {dest}")
    return dest


def install_host(
    source: str | None = None,
    *,
    version: str,
    launch: bool = True,
    console: Console | None = None,
) -> int:
    """Install the prebuilt host APK on a connected device (production path).

    A generic CPython + framework host is installed once; after that
    ``tempest serve`` pushes app code over LAN with no Android SDK/NDK, Gradle,
    or ``android-host`` source tree. No build happens here.

    Args:
        source: A local ``.apk`` path or ``http(s)`` URL; ``None`` uses the
            bundled asset, then a download (see :func:`resolve_host_apk`).
        version: The tempestroid version (used for the fallback release URL).
        launch: Launch the host activity after a successful install.
        console: Step reporter for transparent output.

    Returns:
        ``0`` on success.

    Raises:
        ToolchainError: If adb, a device, or the APK cannot be resolved.
        subprocess.CalledProcessError: If install/launch fails.
    """
    con = console or Console()
    adb = _adb()

    with con.step("Checking for a connected device"):
        devices = connected_devices()
        if not devices:
            raise StepError("no ready device (connect one and run `adb devices`)")
        joined = ", ".join(devices)
        con.info(f"device: {joined}")

    apk = resolve_host_apk(source, version=version, console=con)

    with con.step(f"Installing host APK ({apk.name})"):
        con.run_command([adb, "install", "-r", str(apk)])

    if launch:
        with con.step(f"Launching {_HOST_ACTIVITY}"):
            con.run_command([adb, "shell", "am", "start", "-n", _HOST_ACTIVITY])

    con.info("host installed — push your app with: tempest serve <app.py>")
    return 0


def host_installed(adb: str | None = None) -> bool:
    """Report whether the prebuilt host package is already on the device.

    Lets the offline deploy skip a redundant ~50 MB ``adb install`` when the
    host is already present, so repeated ``tempest build`` runs only push app
    source. Never raises — a probe failure is treated as "not installed".

    Args:
        adb: The ``adb`` executable; resolved from ``PATH`` when ``None``.

    Returns:
        ``True`` when ``pm list packages`` reports :data:`_HOST_PACKAGE`.
    """
    exe = adb or shutil.which("adb")
    if exe is None:
        return False
    try:
        out = subprocess.run(  # noqa: S603
            [exe, "shell", "pm", "list", "packages", _HOST_PACKAGE],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return f"package:{_HOST_PACKAGE}" in out.stdout


def deploy_offline(
    app: str | Path,
    *,
    version: str,
    console: Console | None = None,
    fetch_timeout: float = 60.0,
    settle_seconds: float = 5.0,
    force_install: bool = False,
) -> int:
    """Deploy an app to a connected device offline, with no Android toolchain.

    The single ``tempest build`` abstraction: it needs no SDK/NDK, Gradle, or
    ``android-host`` source. It (1) ensures the prebuilt host APK (bundled in the
    wheel, offline) is installed, then (2) pushes the app source **once** over a
    short-lived dev server — ``adb reverse`` + a dev-mode host launch — waits for
    the device to fetch it, and tears the server down. The app keeps running on
    the device; nothing is left listening. Edit + ``tempest serve`` for a
    persistent hot-reload loop instead.

    Args:
        app: Path to the app's Python file (``make_state`` + ``view``).
        version: The tempestroid version (fallback host-APK release URL).
        console: Step reporter for transparent output (a quiet one when ``None``).
        fetch_timeout: Seconds to wait for the device to fetch the pushed source
            before giving up.
        settle_seconds: Grace window kept serving after the device fetches the
            source, so it finishes parsing and mounting the app before the
            short-lived server is torn down.
        force_install: Re-install the host APK even when already present.

    Returns:
        ``0`` on success.

    Raises:
        ToolchainError: If adb or the host APK cannot be resolved.
        FileNotFoundError: If ``app`` does not exist.
        StepError: If no device is connected or the device never fetches the app.
        subprocess.CalledProcessError: If an adb command fails.
    """
    import threading
    import time

    from tempestroid.devserver import DevServer

    con = console or Console()
    adb = _adb()
    source = Path(app).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"app file not found: {source}")

    with con.step("Checking for a connected device"):
        devices = connected_devices()
        if not devices:
            raise StepError("no ready device (connect one and run `adb devices`)")
        con.info(f"device: {', '.join(devices)}")

    if force_install or not host_installed(adb):
        apk = resolve_host_apk(None, version=version, console=con)
        with con.step(f"Installing host APK ({apk.name})"):
            con.run_command([adb, "install", "-r", str(apk)])
    else:
        con.info(f"host already installed ({_HOST_PACKAGE}) — skipping install")

    fetched = threading.Event()
    server = DevServer(
        source,
        host="127.0.0.1",
        port=0,
        log=con.detail,
        on_fetch=fetched.set,
    )
    with con.step(f"Pushing app to device ({source.name})"):
        server.start()
        try:
            # Force-stop the host so it cold-boots and honors the new dev URL: an
            # `am start` against an already-running activity only triggers
            # onNewIntent, leaving the in-process code-push loop polling the
            # previous (now-unreversed) port — the app would never be fetched.
            subprocess.run(  # noqa: S603
                [adb, "shell", "am", "force-stop", _HOST_PACKAGE], check=False
            )
            adb_reverse(server.port)
            launch_host_dev(server.port)
            if not fetched.wait(timeout=fetch_timeout):
                raise StepError(
                    f"device did not fetch the app within {fetch_timeout:.0f}s "
                    "(is the host installed and the screen on?)"
                )
            con.detail("device fetched the app")
            # Keep serving briefly so the device parses + mounts the app before
            # the server goes away (its next poll erroring is harmless once the
            # app is already running).
            time.sleep(settle_seconds)
        finally:
            server.stop()

    con.info(
        "app deployed — running on the device. "
        "For a live hot-reload loop, run: tempest serve <app.py>"
    )
    return 0


def adb_reverse(port: int) -> None:
    """Wire ``adb reverse`` so the device reaches the dev server on localhost.

    Args:
        port: The TCP port the dev server listens on.

    Raises:
        ToolchainError: If ``adb`` is not on ``PATH``.
        subprocess.CalledProcessError: If the reverse command fails.
    """
    adb = _adb()
    subprocess.run(  # noqa: S603
        [adb, "reverse", f"tcp:{port}", f"tcp:{port}"], check=True
    )


def launch_host_dev(port: int) -> None:
    """Launch the host activity in dev mode, pointed at a local dev server.

    The host reads the ``tempest_dev_url`` intent extra and starts its code-push
    client against ``http://localhost:<port>`` (reachable via :func:`adb_reverse`).

    Args:
        port: The dev server port.

    Raises:
        ToolchainError: If ``adb`` is not on ``PATH``.
        subprocess.CalledProcessError: If the launch command fails.
    """
    adb = _adb()
    subprocess.run(  # noqa: S603
        [
            adb,
            "shell",
            "am",
            "start",
            "-n",
            _HOST_ACTIVITY,
            "--es",
            _DEV_URL_EXTRA,
            f"http://localhost:{port}",
        ],
        check=True,
    )
