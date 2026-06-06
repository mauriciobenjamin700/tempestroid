"""Gradle-driven shippable builds: a store AAB and a per-app debug APK.

The store AAB is ``tempest build --release``; the per-app debug APK is the
default ``tempest build``. Both artifacts come from the **same Gradle project**
(``android-host``), so each
carries its **own ``applicationId``** — two apps built by tempestroid install
side by side instead of overwriting each other (an APK repackage can't rewrite
the binary manifest's package, so it can't give each app a distinct id; Gradle
can, via ``-Ptempest.applicationId``). The Play Store additionally wants an
**Android App Bundle** (``.aab``), release-signed — which only ``bundleRelease``
produces. Either way this drives the Gradle project and **prepares whatever the
environment is missing** first:

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
from typing import TYPE_CHECKING

from tempestroid.cli.console import Console, StepError
from tempestroid.cli.setup_env import default_sdk_dir, install_android_sdk, jdk_ok

if TYPE_CHECKING:
    from tempestroid.cli.branding import Branding

__all__ = [
    "ReleaseConfig",
    "derive_app_id",
    "derive_app_name",
    "ensure_release_keystore",
    "ensure_source_checkout",
    "ensure_toolchain",
    "build_aab",
    "build_apk",
    "clean_cache",
]

_REPO_URL = "https://github.com/mauriciobenjamin700/tempestroid"
_CACHE = Path.home() / ".tempestroid"


def clean_cache(*, include_keystore: bool = False) -> list[Path]:
    """Remove tempestroid's rebuildable build caches under ``~/.tempestroid``.

    Clears the extracted host natives, the bundled-host working copy, and the
    cloned source — all of which are re-created on the next build. A stale cache
    after a wheel upgrade is a known cause of build failures, so this gives users
    a one-shot reset instead of ``rm -rf`` by hand.

    The release keystore (``release.jks``) is preserved by default: losing it
    blocks future Play updates. Pass ``include_keystore=True`` to drop it too.

    Args:
        include_keystore: Also delete the cached ``release.jks`` keystore.

    Returns:
        The cache paths that existed and were removed, in display order.

    Raises:
        OSError: If a cache entry exists but cannot be removed (e.g. a file in
            use or a permission error). Callers that want a graceful exit should
            handle it (see :func:`tempestroid.cli.main._run_clean`).
    """
    targets = [
        _CACHE / "host-extracted",
        _CACHE / "host-src",
        _CACHE / "src",
    ]
    if include_keystore:
        targets.append(_CACHE / "release.jks")

    removed: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(target)
    return removed


def derive_app_id(project_name: str) -> str:
    """Derive a default ``applicationId`` from a project name.

    Distinct project names yield distinct ids, so two tempestroid apps install
    side by side. For a store release the publisher should still pass their own
    ``--app-id`` (``com.example.*`` is a placeholder, not publishable).

    Args:
        project_name: The project directory name (e.g. ``"my-todo"``).

    Returns:
        A valid lowercase package id (e.g. ``"com.example.mytodo"``).
    """
    slug = "".join(ch for ch in project_name.lower() if ch.isalnum()) or "app"
    return f"com.example.{slug}"


def derive_app_name(project_name: str) -> str:
    """Derive a human launcher label (the name under the icon) from a project.

    Turns the project directory name into a title-cased label, so two tempestroid
    apps are told apart on the home screen (the ``applicationId`` keeps them
    independent; this is the cosmetic name).

    Args:
        project_name: The project directory name (e.g. ``"my-todo"``).

    Returns:
        A human label (e.g. ``"My Todo"``); ``"App"`` when the name is empty.
    """
    cleaned = project_name.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else "App"


@dataclass(frozen=True)
class ReleaseConfig:
    """The publisher identity + signing for a store release build.

    Attributes:
        app_id: The store ``applicationId`` (e.g. ``com.acme.todo``).
        app_name: The launcher label (the name under the icon).
        version_name: Human version (e.g. ``"1.0.0"``).
        version_code: Monotonic integer version code.
        keystore: Path to the release keystore, or ``None`` to auto-generate.
        key_alias: The key alias inside the keystore.
        store_password: The keystore password.
        key_password: The key password (defaults to the store password).
    """

    app_id: str
    app_name: str = "tempestroid host"
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


def _prepare_sdk_env(con: Console, *, need_ndk: bool = True) -> Path:
    """Resolve a usable Android SDK and force it into the environment for Gradle.

    ``default_sdk_dir`` resolves the SDK (a valid ``ANDROID_SDK_ROOT``/
    ``ANDROID_HOME`` env value, else the system fallback, else the managed dir),
    installing it when incomplete. Then **both** env vars are overwritten to the
    resolved path: a STALE ``ANDROID_HOME``/``ANDROID_SDK_ROOT`` left in the
    user's shell (e.g. a non-existent ``~/Android/Sdk``) must not reach Gradle —
    AGP reads ``ANDROID_HOME`` and would otherwise fail "SDK location not found".
    ``setdefault`` would leave the stale value in place, so this overwrites.

    Args:
        con: Step reporter.
        need_ndk: Whether the NDK is required (the source build needs it; the
            prebuilt-natives build does not, so it only needs ``platform-tools``).

    Returns:
        The resolved SDK directory.

    Raises:
        StepError: If the SDK (+ NDK when required) cannot be prepared.
    """
    sdk = default_sdk_dir()
    missing_pt = not (sdk / "platform-tools").is_dir()
    missing_ndk = need_ndk and not (sdk / "ndk").is_dir()
    if missing_pt or missing_ndk:
        con.info("preparing the Android SDK…")
        install_android_sdk(sdk, console=con)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk)
    os.environ["ANDROID_HOME"] = str(sdk)
    return sdk


def _extract_prebuilt_host(con: Console) -> Path:
    """Resolve the prebuilt host APK and extract it for the prebuilt build mode.

    The host APK already contains every native (``libpython``, the ``_python``
    runtime libs, ``libtempest_host``) plus the CPython stdlib + site-packages —
    so the Gradle build can reuse them and skip the heavy CPython toolchain. This
    resolves the host APK (bundled asset → cache → GitHub release download) and
    unzips it into a per-version cache dir consumed via ``-Ptempest.prebuiltHost``.

    Args:
        con: Step reporter.

    Returns:
        The extracted host directory (contains ``lib/`` + ``assets/python/``).

    Raises:
        StepError: If the host APK cannot be resolved.
    """
    import zipfile

    from tempestroid import __version__
    from tempestroid.cli.packaging import ToolchainError, resolve_host_apk

    try:
        host_apk = resolve_host_apk(None, version=__version__, console=con)
    except (ToolchainError, FileNotFoundError) as exc:
        raise StepError(f"could not resolve the prebuilt host APK: {exc}") from exc
    dest = _CACHE / "host-extracted" / __version__
    marker = dest / "assets" / "python" / "lib"
    if not marker.is_dir():
        with con.step("Extracting prebuilt host natives"):
            shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(host_apk) as zf:
                for info in zf.infolist():
                    if info.filename.startswith(
                        ("lib/", "assets/python/")
                    ) and not info.is_dir():
                        zf.extract(info, dest)
    return dest


def _resolve_host_checkout(con: Console, version: str, *, prebuilt: bool) -> Path:
    """Resolve a usable ``android-host`` Gradle project for the build.

    Order: an existing checkout (``TEMPESTROID_ANDROID_HOST`` / a repo checkout
    found by walking up from the cwd) → the **android-host bundled in the wheel**
    (``tempestroid/_android_host``, copied to a writable cache; prebuilt mode
    only, since it carries no CPython toolchain) → a ``git clone`` of the repo at
    the version tag (from-source, or when no bundled copy exists).

    The bundled copy makes ``tempest build`` work from a plain ``pip install``
    with no ``git`` and always matched to the installed version.

    Args:
        con: Step reporter.
        version: The installed tempestroid version (clone tag ``v<version>``).
        prebuilt: Whether the prebuilt-natives build is in use (allows the
            bundled checkout, which has no ``toolchain/`` scripts).

    Returns:
        The checkout root (the dir containing ``android-host/``).

    Raises:
        StepError: If no checkout can be resolved.
    """
    from importlib import resources

    from tempestroid.cli.packaging import ToolchainError, find_android_host

    try:
        return find_android_host().parent
    except ToolchainError:
        pass
    if prebuilt:
        try:
            bundled = resources.files("tempestroid").joinpath("_android_host")
            gradlew = bundled.joinpath("gradlew")
            if gradlew.is_file():
                cache_root = _CACHE / "host-src"
                target = cache_root / "android-host"
                framework = cache_root / "tempestroid"
                if not (target / "gradlew").is_file() or not framework.is_dir():
                    with con.step("Preparing bundled android-host"):
                        shutil.rmtree(cache_root, ignore_errors=True)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with resources.as_file(bundled) as src:
                            shutil.copytree(src, target)
                        # gradlew must be executable after the copy.
                        (target / "gradlew").chmod(0o755)
                        # The Gradle build re-stages the framework from a sibling
                        # `../tempestroid` (coreSrc). Copy the installed package
                        # there, minus the bundled host + the heavy APK asset.
                        pkg = resources.files("tempestroid")
                        with resources.as_file(pkg) as pkg_src:
                            shutil.copytree(
                                pkg_src,
                                framework,
                                ignore=shutil.ignore_patterns(
                                    "_android_host", "_assets", "__pycache__",
                                    "*.pyc",
                                ),
                            )
                return cache_root
        except (OSError, ModuleNotFoundError):
            pass
    return ensure_source_checkout(version, con)


def _prepare_gradle_build(
    app: str | Path, con: Console, *, prebuilt: bool = True
) -> tuple[Path, Path | None]:
    """Prepare the Gradle build environment and stage the app bundle.

    Ensures a JDK, the Android SDK, and the ``android-host`` source checkout. In
    **prebuilt mode** (the default) it extracts the prebuilt host APK's natives +
    stdlib (no NDK, no CPython toolchain — fast + reliable from a PyPI install);
    otherwise it stages the full CPython toolchain (the heavy from-source path).
    Then it bundles the user's whole project into the host assets.

    Args:
        app: Path to the app's entry Python file.
        con: Step reporter.
        prebuilt: Reuse the prebuilt host natives (``True``, default) instead of
            staging the CPython toolchain from source.

    Returns:
        A ``(host, prebuilt_dir)`` pair — the ``android-host`` Gradle project dir
        and the extracted prebuilt host dir (``None`` in from-source mode).

    Raises:
        StepError: If a prepare step fails (missing JDK, clone failure, …).
    """
    from tempestroid import __version__
    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.packaging import stage_app_bundle

    layout = resolve_project(app)

    # 1. JDK (required by Gradle + keytool) — guided, not auto-installed.
    ok, detail = jdk_ok()
    if not ok:
        raise StepError(f"a JDK is required ({detail}).")

    # 2. SDK (+ NDK only for the from-source build).
    _prepare_sdk_env(con, need_ndk=not prebuilt)

    # 3. android-host Gradle project (existing checkout → bundled → clone).
    checkout = _resolve_host_checkout(con, __version__, prebuilt=prebuilt)
    host = checkout / "android-host"

    # 4. Natives: reuse the prebuilt host (fast) or stage the CPython toolchain.
    prebuilt_dir: Path | None = None
    if prebuilt:
        prebuilt_dir = _extract_prebuilt_host(con)
    else:
        ensure_toolchain(checkout, con)

    # 5. Stage the user's project bundle into the host assets.
    with con.step(f"Bundling project ({layout.entry})"):
        stage_app_bundle(app, host)

    return host, prebuilt_dir


def build_aab(
    app: str | Path,
    config: ReleaseConfig,
    *,
    console: Console | None = None,
    output: Path | None = None,
    branding: Branding | None = None,
    prebuilt: bool = True,
) -> Path:
    """Build a store-ready, release-signed ``.aab`` for ``app``.

    Prepares the environment (SDK, source checkout, prebuilt host natives or the
    CPython toolchain, keystore) as needed, then drives ``gradlew bundleRelease``
    with the app bundled and the publisher's identity/signing applied.

    Args:
        app: Path to the app's entry Python file.
        config: The publisher identity + signing config.
        console: Step reporter.
        output: Output ``.aab`` path; defaults to ``dist/<project>-release.aab``.
        branding: Optional per-app branding (icon + splash) staged into the host
            for the build.
        prebuilt: Reuse the prebuilt host natives (``True``, default; no NDK /
            CPython toolchain) instead of staging the toolchain from source.

    Returns:
        The signed ``.aab`` path.

    Raises:
        StepError: If a prepare step or the build fails.
        subprocess.CalledProcessError: If Gradle fails.
    """
    con = console or Console()
    from tempestroid.cli.branding import Branding, staged_into_host
    from tempestroid.cli.bundle import resolve_project

    layout = resolve_project(app)
    host, prebuilt_dir = _prepare_gradle_build(app, con, prebuilt=prebuilt)
    keystore = ensure_release_keystore(config, con)

    # gradlew bundleRelease with the publisher identity + signing.
    env = dict(os.environ)
    props = [
        f"-Ptempest.applicationId={config.app_id}",
        f"-Ptempest.appLabel={config.app_name}",
        f"-Ptempest.versionName={config.version_name}",
        f"-Ptempest.versionCode={config.version_code}",
        f"-Ptempest.keystore={keystore}",
        f"-Ptempest.keyAlias={config.key_alias}",
        f"-Ptempest.storePassword={config.store_password}",
        f"-Ptempest.keyPassword={config.key_password}",
    ]
    if prebuilt_dir is not None:
        props.append(f"-Ptempest.prebuiltHost={prebuilt_dir}")
    with staged_into_host(host, branding or Branding()), con.step(
        "Gradle bundleRelease (store AAB)"
    ):
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


def build_apk(
    app: str | Path,
    *,
    app_id: str,
    app_name: str = "tempestroid host",
    version_name: str = "1.0.0",
    version_code: int = 1,
    console: Console | None = None,
    output: Path | None = None,
    branding: Branding | None = None,
    prebuilt: bool = True,
) -> Path:
    """Build a shippable, debug-signed ``.apk`` for ``app`` with its own id.

    Prepares the environment (SDK, source checkout, prebuilt host natives or the
    CPython toolchain) as needed, then drives ``gradlew assembleDebug`` stamping
    ``app_id`` as the ``applicationId``. Because each app carries a distinct id,
    two tempestroid APKs install side by side instead of overwriting each other.
    The APK is signed with the standard Android debug keystore (AGP handles this)
    — fine for sharing and sideloading, but not for a Play Store upload (use
    :func:`build_aab` for that).

    By default it builds in **prebuilt-natives mode** — reusing the prebuilt host
    APK's CPython + JNI libs, so it needs only a JDK + the Android SDK (no NDK, no
    CPython toolchain) and works from a plain PyPI install.

    Args:
        app: Path to the app's entry Python file.
        app_id: The ``applicationId`` to stamp (unique per app).
        app_name: The launcher label (the name under the icon).
        version_name: Human version string.
        version_code: Monotonic integer version code.
        console: Step reporter.
        output: Output ``.apk`` path; defaults to ``dist/<project>.apk``.
        branding: Optional per-app branding (icon + splash) staged into the host
            for the build.
        prebuilt: Reuse the prebuilt host natives (``True``, default) instead of
            staging the CPython toolchain from source.

    Returns:
        The debug-signed ``.apk`` path.

    Raises:
        StepError: If a prepare step or the build fails.
        subprocess.CalledProcessError: If Gradle fails.
    """
    con = console or Console()
    from tempestroid.cli.branding import Branding, staged_into_host
    from tempestroid.cli.bundle import resolve_project

    layout = resolve_project(app)
    host, prebuilt_dir = _prepare_gradle_build(app, con, prebuilt=prebuilt)

    env = dict(os.environ)
    props = [
        f"-Ptempest.applicationId={app_id}",
        f"-Ptempest.appLabel={app_name}",
        f"-Ptempest.versionName={version_name}",
        f"-Ptempest.versionCode={version_code}",
    ]
    if prebuilt_dir is not None:
        props.append(f"-Ptempest.prebuiltHost={prebuilt_dir}")
    with staged_into_host(host, branding or Branding()), con.step(
        f"Gradle assembleDebug (applicationId={app_id})"
    ):
        con.run_command(["./gradlew", "assembleDebug", *props], cwd=host, env=env)

    built = host / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if not built.is_file():
        raise StepError(f"build succeeded but no APK at {built}")
    out = output or (Path.cwd() / "dist" / f"{layout.root.name}.apk")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, out)
    con.info(f"APK ({app_id}): {out}")
    return out
