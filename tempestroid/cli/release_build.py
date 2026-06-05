"""Store-ready release build (``tempest build --release``) → signed AAB.

The Play Store wants an **Android App Bundle** (``.aab``), release-signed, with
the publisher's own ``applicationId`` — which only the Gradle ``bundleRelease``
path can produce (an AAB cannot be made by repackaging an APK). So this drives
the ``android-host`` Gradle project, and **prepares whatever the environment is
missing** first:

* **SDK + NDK** — installed via :func:`tempestroid.cli.setup_env.install_android_sdk`.
* **source checkout** (``android-host`` + ``toolchain/`` scripts) — an existing
  checkout, else cloned from the repo at the matching version tag into a cache.
* **CPython toolchain** (``toolchain/dist``: the Android CPython prefix + native
  wheels) — staged via the repo's toolchain scripts when absent. This is the
  heavy step (downloads + native wheel build).
* **release keystore** — a provided one, else a generated cache keystore (the CLI
  prints where it lives; back it up — losing it blocks future Play updates).

Then ``gradlew bundleRelease`` with the app bundled + the publisher's identity,
and the ``.aab`` is copied to ``dist/``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tempestroid.cli.console import Console, StepError

__all__ = [
    "ReleaseConfig",
    "ensure_release_keystore",
    "ensure_source_checkout",
    "ensure_toolchain",
    "build_aab",
]

_REPO_URL = "https://github.com/mauriciobenjamin700/tempestroid"
_CACHE = Path.home() / ".tempestroid"


@dataclass(frozen=True)
class ReleaseConfig:
    """The publisher identity + signing for a store release build.

    Attributes:
        app_id: The store ``applicationId`` (e.g. ``com.acme.todo``).
        version_name: Human version (e.g. ``"1.0.0"``).
        version_code: Monotonic integer version code.
        keystore: Path to the release keystore, or ``None`` to auto-generate.
        key_alias: The key alias inside the keystore.
        store_password: The keystore password.
        key_password: The key password (defaults to the store password).
    """

    app_id: str
    version_name: str = "1.0.0"
    version_code: int = 1
    keystore: Path | None = None
    key_alias: str = "tempest"
    store_password: str = "tempest"
    key_password: str = "tempest"


def ensure_release_keystore(config: ReleaseConfig, console: Console) -> Path:
    """Return a release keystore, generating a cache one when none is given.

    Args:
        config: The release config (its ``keystore`` wins when set).
        console: Step reporter.

    Returns:
        The keystore path.

    Raises:
        StepError: If keytool is unavailable.
    """
    if config.keystore is not None:
        if not config.keystore.is_file():
            raise StepError(f"keystore not found: {config.keystore}")
        return config.keystore
    keystore = _CACHE / "release.jks"
    if keystore.is_file():
        console.info(f"using generated release keystore: {keystore}")
        return keystore
    keytool = shutil.which("keytool")
    if keytool is None:
        raise StepError("keytool not found on PATH (install a JDK).")
    keystore.parent.mkdir(parents=True, exist_ok=True)
    with console.step("Generating release keystore"):
        console.run_command(
            [
                keytool, "-genkeypair", "-keystore", str(keystore),
                "-storepass", config.store_password,
                "-keypass", config.key_password,
                "-alias", config.key_alias,
                "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                "-dname", f"CN={config.app_id},O=tempestroid,C=US",
            ]
        )
    console.info(
        f"generated {keystore} — BACK IT UP. Losing it blocks future Play updates."
    )
    return keystore


def ensure_source_checkout(version: str, console: Console) -> Path:
    """Return a tempestroid source checkout (android-host + toolchain scripts).

    Uses an existing checkout (env ``TEMPESTROID_ANDROID_HOST``'s parent, or one
    found by walking up from the cwd); otherwise clones the repo at the matching
    version tag into the cache.

    Args:
        version: The installed tempestroid version (clone tag ``v<version>``).
        console: Step reporter.

    Returns:
        The checkout root (the dir containing ``android-host/`` + ``toolchain/``).

    Raises:
        StepError: If no checkout exists and the clone fails.
    """
    from tempestroid.cli.packaging import ToolchainError, find_android_host

    try:
        return find_android_host().parent
    except ToolchainError:
        pass
    dest = _CACHE / "src"
    if (dest / "android-host" / "gradlew").is_file():
        console.info(f"using cached source checkout: {dest}")
        return dest
    git = shutil.which("git")
    if git is None:
        raise StepError(
            "no android-host checkout and git is not installed. Install git, or "
            "run from a tempestroid checkout / set TEMPESTROID_ANDROID_HOST."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    tag = f"v{version}"
    with console.step(f"Cloning source ({_REPO_URL} @ {tag})"):
        result = subprocess.run(  # noqa: S603
            [git, "clone", "--depth", "1", "--branch", tag, _REPO_URL, str(dest)],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Fall back to the default branch when the tag is absent.
            subprocess.run(  # noqa: S603
                [git, "clone", "--depth", "1", _REPO_URL, str(dest)], check=True
            )
    return dest


def ensure_toolchain(checkout: Path, console: Console) -> None:
    """Stage the CPython toolchain (``toolchain/dist``) when it is absent.

    Runs the repo's toolchain scripts (fetch the Android CPython prefix, build
    the native wheels, stage site-packages) — the heavy prerequisite the Gradle
    native build links against.

    Args:
        checkout: The source checkout root.
        console: Step reporter.

    Raises:
        StepError: If the toolchain scripts are missing or fail.
    """
    dist = checkout / "toolchain" / "dist"
    prefix = dist / "python" / "arm64-v8a"
    if prefix.is_dir():
        return
    scripts = checkout / "toolchain"
    if not (scripts / "00_fetch_cpython.sh").is_file():
        raise StepError(
            f"toolchain scripts not found under {scripts}; cannot stage CPython. "
            "Use a full source checkout."
        )
    console.info("staging the CPython toolchain (heavy: downloads + wheel build)…")
    with console.step("make toolchain (fetch CPython + build wheels + stage)"):
        console.run_command(
            ["bash", "-lc",
             "cd toolchain && source env.sh && ./00_fetch_cpython.sh && "
             "./01_build_wheels.sh && ./02_stage_deps.sh"],
            cwd=checkout,
        )


def build_aab(
    app: str | Path,
    config: ReleaseConfig,
    *,
    console: Console | None = None,
    output: Path | None = None,
) -> Path:
    """Build a store-ready, release-signed ``.aab`` for ``app``.

    Prepares the environment (SDK/NDK, source checkout, CPython toolchain,
    keystore) as needed, then drives ``gradlew bundleRelease`` with the app
    bundled and the publisher's identity/signing applied.

    Args:
        app: Path to the app's entry Python file.
        config: The publisher identity + signing config.
        console: Step reporter.
        output: Output ``.aab`` path; defaults to ``dist/<project>-release.aab``.

    Returns:
        The signed ``.aab`` path.

    Raises:
        StepError: If a prepare step or the build fails.
        subprocess.CalledProcessError: If Gradle fails.
    """
    con = console or Console()
    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.packaging import stage_app_bundle
    from tempestroid.cli.setup_env import default_sdk_dir, install_android_sdk, jdk_ok

    layout = resolve_project(app)

    # 1. JDK (required by Gradle + keytool) — guided, not auto-installed.
    ok, detail = jdk_ok()
    if not ok:
        raise StepError(f"a JDK is required ({detail}).")

    # 2. SDK + NDK.
    sdk = default_sdk_dir()
    if not (sdk / "ndk").is_dir() or not (sdk / "platform-tools").is_dir():
        con.info("preparing the Android SDK + NDK…")
        install_android_sdk(sdk, console=con)
    os.environ.setdefault("ANDROID_SDK_ROOT", str(sdk))

    # 3. Source checkout (android-host + toolchain scripts).
    from tempestroid import __version__

    checkout = ensure_source_checkout(__version__, con)
    host = checkout / "android-host"

    # 4. CPython toolchain (heavy if absent).
    ensure_toolchain(checkout, con)

    # 5. Release keystore.
    keystore = ensure_release_keystore(config, con)

    # 6. Stage the user's project bundle into the host assets.
    with con.step(f"Bundling project ({layout.entry})"):
        stage_app_bundle(app, host)

    # 7. gradlew bundleRelease with the publisher identity + signing.
    env = dict(os.environ)
    props = [
        f"-Ptempest.applicationId={config.app_id}",
        f"-Ptempest.versionName={config.version_name}",
        f"-Ptempest.versionCode={config.version_code}",
        f"-Ptempest.keystore={keystore}",
        f"-Ptempest.keyAlias={config.key_alias}",
        f"-Ptempest.storePassword={config.store_password}",
        f"-Ptempest.keyPassword={config.key_password}",
    ]
    with con.step("Gradle bundleRelease (store AAB)"):
        con.run_command(["./gradlew", "bundleRelease", *props], cwd=host, env=env)

    built = (
        host / "app" / "build" / "outputs" / "bundle" / "release" / "app-release.aab"
    )
    if not built.is_file():
        raise StepError(f"build succeeded but no AAB at {built}")
    out = output or (Path.cwd() / "dist" / f"{layout.root.name}-release.aab")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, out)
    con.info(f"store AAB: {out}")
    return out
