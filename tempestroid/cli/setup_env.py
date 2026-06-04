"""Configure the Android build environment (``tempest setup``).

Building a shippable APK with ``tempest build`` needs an Android SDK + NDK, a
JDK, and the staged CPython toolchain — more than the offline ``tempest deploy``
path requires. This module probes those prerequisites and, on request, installs
the Android SDK packages (command-line tools + platform-tools + platform +
build-tools + NDK) into a managed directory using Google's headless
``sdkmanager``, so a user who only has Python can get to a working APK build.

What it can and cannot do automatically:

* **Android SDK + NDK + build-tools** — fully scriptable via the official
  ``commandlinetools`` package + ``sdkmanager`` (licenses accepted headlessly).
  ``tempest setup --install`` does this.
* **JDK** — not auto-installed (needs the OS package manager / admin rights);
  the command prints the exact install line for the host OS instead.
* **Staged Python toolchain** (``make toolchain``) — heavy (compiles native
  wheels against the NDK); the command points at it rather than running it.

The pinned versions mirror ``android-host`` (compileSdk 35, AGP 8.7) and
``toolchain/env.sh`` (NDK r27), so the installed SDK matches what the build uses.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from tempestroid.cli.console import Console, StepError
from tempestroid.cli.packaging import (
    PreflightCheck,
    ToolchainError,
    find_android_host,
)

__all__ = [
    "NDK_VERSION",
    "COMPILE_SDK",
    "BUILD_TOOLS",
    "default_sdk_dir",
    "install_target_dir",
    "jdk_ok",
    "probe_build_env",
    "install_android_sdk",
    "setup_build_env",
]

# Versions pinned to match the android-host build (compileSdk 35, AGP 8.7) and
# toolchain/env.sh (NDK r27). Keep in sync if those bump.
NDK_VERSION = "27.3.13750724"
COMPILE_SDK = "35"
BUILD_TOOLS = "35.0.0"
# Google command-line tools build (the bootstrap that provides sdkmanager). A
# pinned, known-good build so the download is reproducible.
_CMDLINE_TOOLS_BUILD = "11076708"
# Minimum JDK major version AGP 8.7 accepts (21 recommended).
_MIN_JDK_MAJOR = 17


# Per-user managed SDK location used when no existing SDK is found.
_MANAGED_SDK = Path.home() / ".tempestroid" / "android-sdk"
# System SDK location on the maintainer's host (mirrors packaging._SDK_FALLBACK).
_SYSTEM_SDK_FALLBACK = Path("/usr/lib/android-sdk")


def default_sdk_dir() -> Path:
    """Return the SDK directory to inspect — the one the build would use.

    Mirrors the build's SDK resolution (``ANDROID_SDK_ROOT`` → ``ANDROID_HOME``
    → the system fallback), so a host that already has a working SDK is reported
    as such instead of being told to reinstall. Falls back to a per-user managed
    location (where ``--install`` writes) when none exists.

    Returns:
        The resolved SDK directory path.
    """
    for env_var in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(env_var)
        if value and Path(value).is_dir():
            return Path(value)
    if _SYSTEM_SDK_FALLBACK.is_dir():
        return _SYSTEM_SDK_FALLBACK
    return _MANAGED_SDK


def install_target_dir(sdk_dir: Path | None) -> Path:
    """Return where ``tempest setup --install`` should write the SDK.

    An explicit ``--sdk-dir`` wins; otherwise ``ANDROID_SDK_ROOT`` when set (even
    if absent — the user pointed there); otherwise the per-user managed dir, so
    the install needs no admin rights (never the read-only system fallback).

    Args:
        sdk_dir: An explicit target, or ``None``.

    Returns:
        The directory to install into.
    """
    if sdk_dir is not None:
        return sdk_dir
    env = os.environ.get("ANDROID_SDK_ROOT")
    if env:
        return Path(env)
    return _MANAGED_SDK


def _cmdline_tools_url() -> str:
    """Return the OS-specific command-line tools download URL.

    Returns:
        The official Google ``commandlinetools`` zip URL for this platform.

    Raises:
        ToolchainError: If the host OS is unsupported.
    """
    if sys.platform.startswith("linux"):
        os_tag = "linux"
    elif sys.platform == "darwin":
        os_tag = "mac"
    elif sys.platform.startswith("win"):
        os_tag = "win"
    else:
        raise ToolchainError(f"unsupported platform for SDK install: {sys.platform}")
    return (
        "https://dl.google.com/android/repository/"
        f"commandlinetools-{os_tag}-{_CMDLINE_TOOLS_BUILD}_latest.zip"
    )


def jdk_ok() -> tuple[bool, str]:
    """Probe for a usable JDK (``java`` on PATH, major >= 17).

    Returns:
        A ``(ok, detail)`` pair: ``detail`` is the version line or the failure
        reason.
    """
    java = shutil.which("java")
    if java is None:
        return False, "java not on PATH"
    try:
        out = subprocess.run(  # noqa: S603
            [java, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run java: {exc}"
    text = out.stderr or out.stdout
    line = text.splitlines()[0] if text else ""
    # Version line looks like: openjdk version "21.0.3" ... → grab the major.
    major = 0
    if '"' in line:
        token = line.split('"', 2)[1]
        head = token.lstrip("1.").split(".", 1)[0]
        major = int(head) if head.isdigit() else 0
    if major and major < _MIN_JDK_MAJOR:
        return False, f"{line} (need JDK {_MIN_JDK_MAJOR}+)"
    return True, line or str(java)


def _jdk_install_hint() -> str:
    """Return the OS-specific JDK install command for the remediation plan.

    Returns:
        A copy-pasteable install command for a JDK 21.
    """
    if sys.platform == "darwin":
        return "brew install openjdk@21"
    if sys.platform.startswith("win"):
        return "winget install --id EclipseAdoptium.Temurin.21.JDK"
    return "sudo apt-get install -y openjdk-21-jdk  (or your distro's JDK 21)"


def _sdkmanager(sdk_dir: Path) -> Path | None:
    """Locate the ``sdkmanager`` binary under an SDK dir's command-line tools.

    Args:
        sdk_dir: The SDK root to look under.

    Returns:
        The ``sdkmanager`` path if present, else ``None``.
    """
    name = "sdkmanager.bat" if sys.platform.startswith("win") else "sdkmanager"
    candidate = sdk_dir / "cmdline-tools" / "latest" / "bin" / name
    return candidate if candidate.is_file() else None


def probe_build_env(
    sdk_dir: Path | None = None, *, host: Path | None = None
) -> list[PreflightCheck]:
    """Probe everything ``tempest build`` needs, with install hints.

    Checks the JDK, the SDK root + its platform-tools/NDK/build-tools, the
    command-line tools, the staged Python toolchain, and the ``android-host``
    checkout. Each :class:`PreflightCheck` carries an actionable hint so the
    caller can render a remediation plan.

    Args:
        sdk_dir: SDK root to inspect; defaults to :func:`default_sdk_dir`.
        host: A known ``android-host`` root; auto-located when ``None``.

    Returns:
        One :class:`PreflightCheck` per probe, in display order.
    """
    sdk = sdk_dir or default_sdk_dir()
    checks: list[PreflightCheck] = []

    ok, detail = jdk_ok()
    jdk_hint = "" if ok else f"install: {_jdk_install_hint()}"
    checks.append(PreflightCheck("jdk", ok, detail, jdk_hint))

    sdk_exists = sdk.is_dir()
    checks.append(
        PreflightCheck(
            "android-sdk",
            sdk_exists,
            str(sdk) if sdk_exists else f"{sdk} (absent)",
            "" if sdk_exists else "run `tempest setup --install` to create it.",
        )
    )

    has_sdkmanager = _sdkmanager(sdk) is not None
    checks.append(
        PreflightCheck(
            "cmdline-tools",
            has_sdkmanager,
            "sdkmanager present" if has_sdkmanager else "sdkmanager missing",
            "" if has_sdkmanager else "run `tempest setup --install`.",
        )
    )

    ndk_dir = sdk / "ndk" / NDK_VERSION
    has_ndk = ndk_dir.is_dir()
    checks.append(
        PreflightCheck(
            "ndk",
            has_ndk,
            str(ndk_dir) if has_ndk else f"ndk;{NDK_VERSION} missing",
            "" if has_ndk else "run `tempest setup --install`.",
        )
    )

    bt_dir = sdk / "build-tools" / BUILD_TOOLS
    has_bt = bt_dir.is_dir()
    checks.append(
        PreflightCheck(
            "build-tools",
            has_bt,
            str(bt_dir) if has_bt else f"build-tools;{BUILD_TOOLS} missing",
            "" if has_bt else "run `tempest setup --install`.",
        )
    )

    staged = _staged_toolchain_present()
    checks.append(
        PreflightCheck(
            "python-toolchain",
            staged,
            "toolchain/dist staged" if staged else "toolchain/dist absent",
            "" if staged else "run `make toolchain` (CPython 3.14 + native wheels).",
        )
    )

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

    return checks


def _staged_toolchain_present() -> bool:
    """Report whether the staged CPython toolchain exists in a checkout.

    Returns:
        ``True`` when ``toolchain/dist`` holds staged artifacts; ``False`` when
        absent or not in a checkout.
    """
    try:
        host = find_android_host()
    except ToolchainError:
        return False
    dist = host.parent / "toolchain" / "dist"
    return dist.is_dir() and any(dist.iterdir())


def install_android_sdk(
    sdk_dir: Path, *, console: Console | None = None
) -> Path:
    """Install the Android SDK packages needed to build into ``sdk_dir``.

    Downloads Google's command-line tools (if absent), accepts the SDK licenses
    headlessly, then installs ``platform-tools``, the ``android-{COMPILE_SDK}``
    platform, ``build-tools;{BUILD_TOOLS}`` and ``ndk;{NDK_VERSION}`` — matching
    what the ``android-host`` Gradle build uses. Requires a JDK on PATH
    (``sdkmanager`` runs on Java).

    Args:
        sdk_dir: The SDK root to install into (created if missing).
        console: Step reporter for transparent output.

    Returns:
        The SDK directory.

    Raises:
        StepError: If a JDK is missing.
        ToolchainError: If the platform is unsupported or a download fails.
        subprocess.CalledProcessError: If an ``sdkmanager`` command fails.
    """
    con = console or Console()
    ok, detail = jdk_ok()
    if not ok:
        raise StepError(
            f"a JDK is required first ({detail}). Install: {_jdk_install_hint()}"
        )

    sdk_dir.mkdir(parents=True, exist_ok=True)
    if _sdkmanager(sdk_dir) is None:
        _install_cmdline_tools(sdk_dir, con)

    sdkmanager = _sdkmanager(sdk_dir)
    if sdkmanager is None:
        raise ToolchainError("sdkmanager not found after installing command-line tools")

    root_arg = f"--sdk_root={sdk_dir}"
    with con.step("Accepting SDK licenses"):
        # sdkmanager --licenses prompts y/N repeatedly; feed acceptances.
        subprocess.run(  # noqa: S603
            [str(sdkmanager), root_arg, "--licenses"],
            check=False,
            input="y\n" * 100,
            text=True,
            capture_output=True,
        )

    packages = [
        "platform-tools",
        f"platforms;android-{COMPILE_SDK}",
        f"build-tools;{BUILD_TOOLS}",
        f"ndk;{NDK_VERSION}",
    ]
    with con.step(f"Installing SDK packages ({', '.join(packages)})"):
        con.run_command([str(sdkmanager), root_arg, *packages])

    return sdk_dir


def _install_cmdline_tools(sdk_dir: Path, console: Console) -> None:
    """Download + unpack the command-line tools into ``sdk_dir``.

    The zip extracts to ``cmdline-tools/``; ``sdkmanager`` expects it under
    ``cmdline-tools/latest/``, so the contents are moved there.

    Args:
        sdk_dir: The SDK root to install the tools under.
        console: Step reporter.

    Raises:
        ToolchainError: If the download fails.
    """
    url = _cmdline_tools_url()
    dest_zip = sdk_dir / "cmdline-tools.zip"
    with console.step(f"Downloading command-line tools ({url})"):
        try:
            urllib.request.urlretrieve(url, dest_zip)  # noqa: S310 - https guarded
        except (urllib.error.URLError, OSError) as exc:
            dest_zip.unlink(missing_ok=True)
            raise ToolchainError(
                f"failed to download command-line tools: {exc}"
            ) from exc

    with console.step("Unpacking command-line tools"):
        tools_root = sdk_dir / "cmdline-tools"
        extracted = tools_root / "cmdline-tools"
        latest = tools_root / "latest"
        with zipfile.ZipFile(dest_zip) as archive:
            archive.extractall(tools_root)
        if latest.exists():
            shutil.rmtree(latest)
        # The archive unpacks to cmdline-tools/cmdline-tools/* — promote to latest/.
        extracted.rename(latest)
        dest_zip.unlink(missing_ok=True)


def setup_build_env(
    *,
    sdk_dir: Path | None = None,
    install: bool = False,
    console: Console | None = None,
) -> int:
    """Probe (and optionally install) the Android build environment.

    Without ``install`` this only diagnoses: it prints a per-prerequisite
    report and a remediation plan. With ``install`` it sets up the Android SDK +
    NDK into ``sdk_dir`` (JDK and the staged Python toolchain are still guided,
    not auto-run), then re-probes and prints the ``ANDROID_SDK_ROOT`` to export.

    Args:
        sdk_dir: SDK root to inspect/install into; defaults to
            :func:`default_sdk_dir`.
        install: Install the Android SDK packages when ``True``.
        console: Step reporter for transparent output.

    Returns:
        ``0`` when the environment is build-ready (or the install succeeded),
        else ``1`` (missing prerequisites that need manual steps).

    Raises:
        StepError: If an install step's precondition fails (e.g. no JDK).
        subprocess.CalledProcessError: If an install command fails.
    """
    con = console or Console()
    # Inspect the SDK the build would use; install into a writable target.
    sdk = install_target_dir(sdk_dir) if install else (sdk_dir or default_sdk_dir())

    if install:
        con.info(f"Setting up the Android build environment in {sdk}")
        ok, detail = jdk_ok()
        if not ok:
            con.fail(f"jdk: {detail}")
            con.info(f"  → install a JDK first: {_jdk_install_hint()}")
            return 1
        install_android_sdk(sdk, console=con)
        con.info("Android SDK + NDK installed. Add this to your shell profile:")
        con.info(f"  export ANDROID_SDK_ROOT={sdk}")

    con.info("Build environment check:")
    checks = probe_build_env(sdk)
    ready = True
    for check in checks:
        if check.ok:
            con.info(f"  ✓ {check.name}: {check.detail}")
        else:
            ready = False
            con.fail(f"  ✗ {check.name}: {check.detail}")
            if check.hint:
                con.info(f"      → {check.hint}")

    if ready:
        con.info("ready — `tempest build <app>` can produce a shippable APK.")
        return 0
    if not install:
        con.info(
            "run `tempest setup --install` to auto-install the Android SDK + NDK "
            "(JDK + `make toolchain` are guided above)."
        )
    return 1
