"""Build a shippable APK by repackaging the prebuilt host — no Gradle needed.

A PyPI install has no ``android-host`` Gradle project, so it cannot build the
host from source. But it does not need to: the prebuilt host APK already knows
how to boot a project bundle dropped at ``assets/tempest_app_bundle.zip``. So
``tempest build`` produces a distributable APK by **repackaging** that prebuilt
host — inject the user's project bundle into a copy of it, then re-align and
re-sign — using only the Android SDK's ``zipalign`` + ``apksigner`` (no NDK, no
Gradle, no ``android-host`` checkout). The result runs the user's app standalone
and can be handed to anyone (debug-signed — fine for sideloaded testing).

Native ``.so`` entries are copied with their original compression (the host APK
stores them uncompressed for ``extractNativeLibs=false``); ``zipalign`` restores
their alignment after the rewrite.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from tempestroid.cli.console import Console, StepError

__all__ = [
    "ApkToolError",
    "find_build_tool",
    "inject_bundle",
    "ensure_debug_keystore",
    "repackage_host_apk",
]

# Asset path inside the APK the host's MainActivity extracts and runs.
_BUNDLE_ASSET = "assets/tempest_app_bundle.zip"
# Where the SDK lives when ANDROID_SDK_ROOT is unset (mirrors packaging).
_SDK_FALLBACK = "/usr/lib/android-sdk"


class ApkToolError(RuntimeError):
    """Raised when an SDK build-tool or signing prerequisite is missing."""


def _sdk_root() -> Path:
    """Resolve the Android SDK root.

    Returns:
        The SDK directory.

    Raises:
        ApkToolError: If no SDK can be located.
    """
    for var in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(var)
        if value and Path(value).is_dir():
            return Path(value)
    if Path(_SDK_FALLBACK).is_dir():
        return Path(_SDK_FALLBACK)
    raise ApkToolError(
        "no Android SDK found (need zipalign + apksigner). Set ANDROID_SDK_ROOT, "
        "or run `tempest setup --install`."
    )


def find_build_tool(name: str) -> Path:
    """Locate an SDK build-tool (e.g. ``zipalign``, ``apksigner``).

    Picks the highest installed ``build-tools/<version>/`` that contains the tool.

    Args:
        name: The tool's executable name.

    Returns:
        The tool's path.

    Raises:
        ApkToolError: If no build-tools version provides the tool.
    """
    build_tools = _sdk_root() / "build-tools"
    if build_tools.is_dir():
        for version in sorted(build_tools.iterdir(), reverse=True):
            candidate = version / name
            if candidate.is_file():
                return candidate
    raise ApkToolError(
        f"{name} not found under {build_tools}. Install build-tools "
        "(`tempest setup --install`)."
    )


def ensure_debug_keystore(console: Console | None = None) -> Path:
    """Return the Android debug keystore, generating it if absent.

    The standard ``~/.android/debug.keystore`` (alias ``androiddebugkey``,
    storepass/keypass ``android``) — the same key Android Studio uses for debug
    builds, so repackaged APKs install like any debug build.

    Args:
        console: Step reporter for the generate step.

    Returns:
        The keystore path.

    Raises:
        ApkToolError: If generation fails.
    """
    con = console or Console()
    keystore = Path.home() / ".android" / "debug.keystore"
    if keystore.is_file():
        return keystore
    keystore.parent.mkdir(parents=True, exist_ok=True)
    keytool = shutil.which("keytool")
    if keytool is None:
        raise ApkToolError("keytool not found on PATH (install a JDK).")
    with con.step("Generating debug keystore"):
        con.run_command(
            [
                keytool, "-genkeypair", "-keystore", str(keystore),
                "-storepass", "android", "-keypass", "android",
                "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US",
            ]
        )
    return keystore


def inject_bundle(host_apk: Path, bundle: bytes, dest: Path) -> None:
    """Copy ``host_apk`` to ``dest`` with the project bundle injected.

    Rewrites the zip, dropping the old signature (``META-INF/*.SF/.RSA/.MF``) and
    any prior bundle, adding ``assets/tempest_app_bundle.zip``. Each surviving
    entry keeps its original compression so native ``.so`` stay uncompressed.

    Args:
        host_apk: The prebuilt host APK to repackage.
        bundle: The project bundle ``.zip`` bytes.
        dest: The output (unsigned, unaligned) APK path.
    """
    with zipfile.ZipFile(host_apk) as src, zipfile.ZipFile(dest, "w") as out:
        for info in src.infolist():
            name = info.filename
            if name.startswith("META-INF/") and name.rsplit(".", 1)[-1] in {
                "SF", "RSA", "DSA", "EC", "MF",
            }:
                continue  # drop the old signature — we re-sign
            if name == _BUNDLE_ASSET:
                continue  # replace any prior bundle
            data = src.read(name)
            # Preserve the source entry's compression (STORED for .so etc.).
            new_info = zipfile.ZipInfo(name, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            out.writestr(new_info, data)
        bundle_info = zipfile.ZipInfo(_BUNDLE_ASSET, date_time=(1980, 1, 1, 0, 0, 0))
        bundle_info.compress_type = zipfile.ZIP_DEFLATED
        out.writestr(bundle_info, bundle)


def repackage_host_apk(
    host_apk: Path,
    bundle: bytes,
    out_apk: Path,
    *,
    console: Console | None = None,
) -> Path:
    """Repackage the prebuilt host APK with the user's bundle, signed + aligned.

    Inject the bundle, ``zipalign``, then ``apksigner`` with the debug keystore.
    Uses only the Android SDK build-tools — no Gradle / NDK / android-host.

    Args:
        host_apk: The prebuilt host APK (from :func:`resolve_host_apk`).
        bundle: The project bundle ``.zip`` bytes (from ``build_bundle``).
        out_apk: The signed, shippable APK to write.
        console: Step reporter.

    Returns:
        ``out_apk``.

    Raises:
        ApkToolError: If a build-tool or the keystore is missing.
        subprocess.CalledProcessError: If align/sign fails.
    """
    con = console or Console()
    zipalign = find_build_tool("zipalign")
    apksigner = find_build_tool("apksigner")
    keystore = ensure_debug_keystore(con)

    out_apk.parent.mkdir(parents=True, exist_ok=True)
    work = out_apk.with_suffix(".unsigned.apk")
    aligned = out_apk.with_suffix(".aligned.apk")

    with con.step(f"Injecting project bundle ({len(bundle)} bytes)"):
        inject_bundle(host_apk, bundle, work)

    with con.step("Aligning (zipalign)"):
        con.run_command([str(zipalign), "-p", "-f", "4", str(work), str(aligned)])

    with con.step("Signing (apksigner, debug key)"):
        con.run_command(
            [
                str(apksigner), "sign",
                "--ks", str(keystore),
                "--ks-pass", "pass:android",
                "--ks-key-alias", "androiddebugkey",
                "--key-pass", "pass:android",
                "--out", str(out_apk),
                str(aligned),
            ]
        )

    work.unlink(missing_ok=True)
    aligned.unlink(missing_ok=True)
    Path(str(out_apk) + ".idsig").unlink(missing_ok=True)
    if not out_apk.is_file():
        raise StepError(f"signing produced no APK at {out_apk}")
    return out_apk
