"""``tempest`` command-line entry point (Typer).

Wires every ``tempest`` sub-command behind a single :class:`typer.Typer`
``app``, mirroring the ``tempest-fastapi-sdk`` CLI conventions (global
``--version``/``-V`` flag plus a ``version`` command, ``no_args_is_help``,
rich markup). ``tempest dev`` runs the interactive simulator cockpit (phase
A5). ``tempest serve`` pushes an app to a device over LAN (phase B5). The
phase-C packaging commands — ``new`` (scaffold), ``build`` (APK), ``run``
(install + logcat) — drive the ``android-host`` Gradle project and ``adb``;
``doctor`` probes their prerequisites without building. ``build``/``run``/
``dev`` accept ``-v``/``--verbose`` for raw command streaming (see
:mod:`tempestroid.cli.console`). Qt is imported lazily inside ``dev`` so
``tempest --help`` works without the optional ``qt`` extra.
"""

from __future__ import annotations

from typing import Annotated

import typer

__all__ = ["app", "main"]

app: typer.Typer = typer.Typer(
    name="tempest",
    help="Build native Android apps in typed Python.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _print_version(value: bool) -> None:
    """Print the framework version and exit.

    Args:
        value: True when ``--version`` is passed.

    Raises:
        typer.Exit: Always when ``value`` is True.
    """
    if value:
        from tempestroid import __version__

        typer.echo(f"tempest {__version__}")
        raise typer.Exit()


@app.callback()
def _root(  # pyright: ignore[reportUnusedFunction]  # wired by Typer via the decorator
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the framework version and exit.",
            callback=_print_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Root callback wiring global flags such as ``--version``."""


@app.command("version")
def version_cmd() -> None:
    """Show the framework version (alias of ``--version``)."""
    from tempestroid import __version__

    typer.echo(f"tempest {__version__}")


@app.command("dev")
def dev_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print full tracebacks when a save fails to reload.",
        ),
    ] = False,
) -> None:
    """Run the simulator dev loop."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_dev(resolved, verbose))


@app.command("serve")
def serve_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind address (default: 0.0.0.0)."),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", help="TCP port (default: 8765)."),
    ] = 8765,
    no_launch: Annotated[
        bool,
        typer.Option(
            "--no-launch",
            help="Just serve; do not auto `adb reverse` + launch the host in "
            "dev mode (launch it yourself).",
        ),
    ] = False,
) -> None:
    """Serve an app to a device over LAN (code-push + log relay)."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_serve(resolved, host, port, launch=not no_launch))


@app.command("install")
def install_cmd(
    source: Annotated[
        str | None,
        typer.Argument(
            metavar="[SOURCE]",
            help="Local .apk path or http(s) URL. Default: the host APK bundled "
            "in the package (offline). Override via TEMPESTROID_HOST_APK[_URL].",
        ),
    ] = None,
    no_launch: Annotated[
        bool,
        typer.Option("--no-launch", help="Install only; do not launch the host."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Install the prebuilt host APK on a device (no Android SDK/NDK needed)."""
    raise typer.Exit(_run_install(source, launch=not no_launch, verbose=verbose))


@app.command("spec")
def spec_cmd() -> None:
    """Print the typed contract (widgets/events) as JSON."""
    import json

    from tempestroid import introspect

    print(json.dumps(introspect(), indent=2))
    raise typer.Exit(0)


@app.command("new")
def new_cmd(
    name: Annotated[
        str,
        typer.Argument(
            help="Project name for a new subdirectory; use a dot to scaffold in "
            "the current directory (the default).",
        ),
    ] = ".",
    into: Annotated[
        str,
        typer.Option(
            "--into",
            help="Parent directory for a named project (default: current dir).",
        ),
    ] = ".",
) -> None:
    """Scaffold a fully configured tempestroid app."""
    raise typer.Exit(_run_new(name, into))


@app.command("build")
def build_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output", "-o", help="Output path (default: dist/<project>.apk|.aab)."
        ),
    ] = None,
    release: Annotated[
        bool,
        typer.Option(
            "--release",
            help="Build a store-ready, release-signed AAB (Gradle); prepares the "
            "environment (SDK/NDK, source, toolchain, keystore) if missing.",
        ),
    ] = False,
    app_id: Annotated[
        str | None,
        typer.Option(
            "--app-id",
            help="applicationId (e.g. com.acme.todo). Each app needs its own so "
            "two tempestroid APKs install side by side; derived from the project "
            "name when omitted.",
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app-name",
            help="Launcher label (the name under the icon); derived from the "
            "project name when omitted.",
        ),
    ] = None,
    app_version: Annotated[
        str,
        typer.Option("--app-version", help="versionName (default 1.0.0)."),
    ] = "1.0.0",
    version_code: Annotated[
        int,
        typer.Option("--version-code", help="versionCode (default 1)."),
    ] = 1,
    keystore: Annotated[
        str | None,
        typer.Option("--keystore", help="Release keystore (default: auto-generated)."),
    ] = None,
    fast: Annotated[
        bool,
        typer.Option(
            "--fast",
            "-f",
            help="Skip Gradle: repackage the prebuilt host (no SDK/NDK) into a "
            "shippable APK. Fast, but every app keeps the shared id "
            "`org.tempestroid.host`, so apps overwrite each other on a device — "
            "use it to iterate on one app, not to ship several side by side.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full tool output.",
        ),
    ] = False,
) -> None:
    """Build a shippable artifact with the whole project baked in.

    Default: a self-contained, debug-signed **APK** via Gradle `assembleDebug`,
    stamped with its own `--app-id` (derived from the project name when omitted)
    so two tempestroid apps install side by side instead of overwriting each
    other. Hand it to anyone; runs with no dev server.

    With `--release`: a store-ready, release-signed **AAB** (Play Store format)
    via Gradle `bundleRelease`, stamped with `--app-id`/`--app-version`.

    With `--fast`: skip Gradle and repackage the prebuilt host APK (just the SDK
    build-tools, no NDK/source/toolchain). Much faster, but the APK keeps the
    shared `org.tempestroid.host` id — good for iterating on a single app, not
    for shipping several side by side. `tempest deploy` covers the same
    toolchain-free path when you only need it on your own connected device.

    The Gradle paths **prepare whatever is missing** (SDK/NDK, source checkout,
    CPython toolchain, release keystore) on first run.
    """
    resolved = _resolve_app_or_exit(app_path)
    if release:
        raise typer.Exit(
            _run_release(resolved, app_id, app_name, app_version, version_code,
                         keystore, output, verbose)
        )
    if fast:
        raise typer.Exit(_run_build_fast(resolved, output, verbose))
    raise typer.Exit(
        _run_build(resolved, app_id, app_name, app_version, version_code, output,
                   verbose)
    )


@app.command("deploy")
def deploy_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    force_install: Annotated[
        bool,
        typer.Option(
            "--force-install",
            help="Re-install the host APK even if it is already on the device.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Deploy an app to a connected device — offline, no Android SDK/NDK.

    Installs the prebuilt host (bundled in the wheel) if needed, pushes the whole
    project once, launches it, and exits. Great for testing on your own device.
    Use `tempest serve` for live hot reload, or `tempest build` to produce a
    shippable APK (needs the toolchain).
    """
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_deploy(resolved, force_install, verbose))


@app.command("run")
def run_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    app_id: Annotated[
        str | None,
        typer.Option(
            "--app-id",
            help="applicationId (derived from the project name when omitted).",
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app-name",
            help="Launcher label (derived from the project name when omitted).",
        ),
    ] = None,
    app_version: Annotated[
        str,
        typer.Option("--app-version", help="versionName (default 1.0.0)."),
    ] = "1.0.0",
    version_code: Annotated[
        int,
        typer.Option("--version-code", help="versionCode (default 1)."),
    ] = 1,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Build a shippable APK, install it on a device, and stream logs."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(
        _run_run(resolved, app_id, app_name, app_version, version_code, verbose)
    )


@app.command("doctor")
def doctor_cmd(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show resolution hints."),
    ] = False,
) -> None:
    """Check the Android build/run prerequisites and exit."""
    raise typer.Exit(_run_doctor(verbose))


@app.command("setup")
def setup_cmd(
    install: Annotated[
        bool,
        typer.Option(
            "--install",
            help="Auto-install the Android SDK + NDK into --sdk-dir (needs a JDK).",
        ),
    ] = False,
    sdk_dir: Annotated[
        str | None,
        typer.Option(
            "--sdk-dir",
            help="SDK directory to inspect/install into "
            "(default: $ANDROID_SDK_ROOT or ~/.tempestroid/android-sdk).",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Echo raw commands + full output."),
    ] = False,
) -> None:
    """Configure the Android build environment for `tempest build`.

    Without `--install` it diagnoses what's missing (JDK, SDK, NDK, build-tools,
    staged toolchain) and prints a remediation plan. With `--install` it installs
    the Android SDK + NDK into a managed directory (the JDK and `make toolchain`
    stay guided). Not needed for the offline `tempest deploy` / `serve` paths.
    """
    raise typer.Exit(_run_setup(install, sdk_dir, verbose))


def _resolve_app_or_exit(app_path: str | None) -> str:
    """Resolve the app path from the argument or project config, or exit.

    Args:
        app_path: An explicit path, or ``None`` to read ``[tool.tempest] app``.

    Returns:
        The resolved app file path.

    Raises:
        typer.Exit: With code ``1`` when no app can be resolved.
    """
    from tempestroid.cli.project import AppResolutionError, resolve_app

    try:
        return resolve_app(app_path)
    except AppResolutionError as exc:
        print(exc)
        raise typer.Exit(1) from exc


def _run_dev(app: str, verbose: bool) -> int:
    """Dispatch to the Qt dev cockpit, importing Qt lazily.

    Args:
        app: Path to the app file.
        verbose: Print full tracebacks when a save fails to reload.

    Returns:
        The process exit code.
    """
    try:
        from tempestroid.renderers.qt import run_dev
    except ImportError:
        print(
            "`tempest dev` needs the `qt` extra. Install it with: "
            'uv sync --extra qt  (or  pip install "tempestroid[qt]").'
        )
        return 1
    return run_dev(app, verbose=verbose)


def _lan_ip() -> str:
    """Best-effort LAN IP for the device to reach this machine.

    Returns:
        The local IP, or ``127.0.0.1`` if it cannot be determined.
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _run_serve(app: str, host: str, port: int, *, launch: bool = True) -> int:
    """Serve an app to a device and relay its logs until interrupted.

    When a device is connected and ``launch`` is set, this closes the loop
    automatically: it wires ``adb reverse`` and launches the prebuilt host in
    dev mode pointed at this server, so ``tempest install`` + ``tempest serve``
    is all that's needed to run on hardware (no SDK/NDK or source build).

    Args:
        app: Path to the app file.
        host: Bind address.
        port: TCP port.
        launch: Auto ``adb reverse`` + launch the host in dev mode when a device
            is present. Set ``False`` to only serve.

    Returns:
        The process exit code.
    """
    import subprocess
    import threading
    from pathlib import Path

    from tempestroid.cli.packaging import (
        ToolchainError,
        adb_reverse,
        connected_devices,
        launch_host_dev,
    )
    from tempestroid.devserver import DevServer, render_qr

    server = DevServer(app, host=host, port=port)
    try:
        server.start()
    except OSError as exc:
        print(f"could not start dev server on {host}:{port}: {exc}")
        return 1

    lan_url = f"http://{_lan_ip()}:{server.port}"
    devices = connected_devices()
    device_line = ", ".join(devices) if devices else "none (connect one for USB push)"
    print(render_qr(lan_url))
    print(
        f"tempest dev server on port {server.port}.\n"
        f"  App:     {Path(app).resolve()}\n"
        f"  Devices: {device_line}\n"
        f"  LAN:     {lan_url}\n"
        f"  USB:     adb reverse tcp:{server.port} tcp:{server.port} "
        f"→ http://localhost:{server.port}\n"
        "Edit + save the app file to hot-restart on device. Ctrl-C to stop."
    )
    if launch and devices:
        try:
            adb_reverse(server.port)
            launch_host_dev(server.port)
            print(
                f"launched the host in dev mode on {devices[0]} "
                f"(adb reverse :{server.port} + tempest_dev_url)."
            )
        except (ToolchainError, subprocess.CalledProcessError) as exc:
            print(
                f"could not auto-launch the host ({exc}); launch it manually:\n"
                f"  adb reverse tcp:{server.port} tcp:{server.port}\n"
                f"  adb shell am start -n org.tempestroid.host/.MainActivity "
                f"--es tempest_dev_url http://localhost:{server.port}"
            )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopping dev server.")
    finally:
        server.stop()
    return 0


def _run_install(source: str | None, *, launch: bool, verbose: bool) -> int:
    """Install the prebuilt host APK on a device, reporting the outcome.

    Args:
        source: A local ``.apk`` path or ``http(s)`` URL; ``None`` uses the host
            APK bundled in the package (offline), falling back to a download.
        launch: Launch the host activity after installing.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid import __version__
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, install_host

    console = Console(verbose=verbose)
    try:
        return install_host(
            source, version=__version__, launch=launch, console=console
        )
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
        console.fail(f"install failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"adb command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_new(name: str, into: str) -> int:
    """Scaffold a fully configured app project, reporting the outcome.

    Args:
        name: The project name, or ``"."`` to scaffold in the current directory.
        into: Parent directory to create a named project under.

    Returns:
        The process exit code.
    """
    from tempestroid.cli.scaffold import scaffold

    try:
        result = scaffold(name, parent=into)
    except (ValueError, FileExistsError) as exc:
        print(f"cannot scaffold: {exc}")
        return 1
    where = "." if result.in_place else result.root.name
    cd_hint = "" if result.in_place else f"  cd {where}\n"
    print(
        f"created {result.name} in {result.root}\n"
        f"{cd_hint}"
        "  uv sync                  # install tempestroid + the Qt simulator\n"
        "  uv run tempest dev       # simulator + hot reload (reads pyproject)\n"
        "  uv run tempest install   # adb-install the bundled host (offline)\n"
        "  uv run tempest serve     # push to the device + auto-launch"
    )
    return 0


def _run_build_fast(app: str, output: str | None, verbose: bool) -> int:
    """Build a shippable APK by repackaging the prebuilt host (no Gradle).

    The `--fast` path: bundle the whole project and inject it into the prebuilt
    host APK, re-aligned + re-signed via the SDK build-tools only — no Gradle,
    NDK, source checkout, or CPython toolchain. The APK keeps the shared
    ``org.tempestroid.host`` id (an APK repackage cannot rewrite the binary
    manifest's package), so it is for iterating on a single app, not for shipping
    several side by side (use the default Gradle build with ``--app-id`` for
    that). See :func:`tempestroid.cli.packaging.package_app_apk`.

    Args:
        app: Path to the app's entry file to bundle.
        output: Output APK path, or ``None`` for ``dist/<project>.apk``.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid import __version__
    from tempestroid.cli.apk_repack import ApkToolError
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, package_app_apk

    console = Console(verbose=verbose)
    try:
        package_app_apk(
            app,
            version=__version__,
            console=console,
            output=Path(output) if output else None,
        )
    except StepError:
        return 1
    except (ApkToolError, ToolchainError, FileNotFoundError) as exc:
        console.fail(f"build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"apk packaging failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_build(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    output: str | None,
    verbose: bool,
) -> int:
    """Build a shippable, debug-signed APK via Gradle, reporting the outcome.

    Bundles the whole project into the ``android-host`` Gradle project and runs
    ``assembleDebug`` stamping a unique ``applicationId`` (derived from the
    project name when ``app_id`` is ``None``) so two tempestroid APKs install
    side by side. Prepares the env (SDK/NDK, source, toolchain) as needed. See
    :func:`tempestroid.cli.release_build.build_apk`.

    Args:
        app: Path to the app's entry file to bundle.
        app_id: The applicationId, or ``None`` to derive one from the project.
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The versionName.
        version_code: The versionCode.
        output: Output APK path, or ``None`` for ``dist/<project>.apk``.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.release_build import build_apk, derive_app_id, derive_app_name

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id or derive_app_id(project_name)
    resolved_name = app_name or derive_app_name(project_name)
    try:
        build_apk(
            app,
            app_id=resolved_id,
            app_name=resolved_name,
            version_name=app_version,
            version_code=version_code,
            console=console,
            output=Path(output) if output else None,
        )
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"gradle assembleDebug failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_release(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    keystore: str | None,
    output: str | None,
    verbose: bool,
) -> int:
    """Build a store-ready release AAB, preparing the environment, reporting outcome.

    Args:
        app: Path to the app's entry file.
        app_id: The store applicationId, or ``None`` to derive one (with a warning).
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The release versionName.
        version_code: The release versionCode.
        keystore: Path to a release keystore, or ``None`` to auto-generate.
        output: Output ``.aab`` path, or ``None`` for the default.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.release_build import (
        ReleaseConfig,
        build_aab,
        derive_app_id,
        derive_app_name,
    )

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id
    if resolved_id is None:
        # Derive a placeholder id from the project name; a real store upload
        # needs the publisher's own id, so warn loudly.
        resolved_id = derive_app_id(project_name)
        console.info(
            f"no --app-id given; using placeholder {resolved_id!r}. Set --app-id "
            "to your own (e.g. com.yourcompany.app) before publishing."
        )
    config = ReleaseConfig(
        app_id=resolved_id,
        app_name=app_name or derive_app_name(project_name),
        version_name=app_version,
        version_code=version_code,
        keystore=Path(keystore) if keystore else None,
    )
    try:
        build_aab(app, config, console=console, output=Path(output) if output else None)
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"release build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"gradle bundleRelease failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_deploy(app: str, force_install: bool, verbose: bool) -> int:
    """Deploy the app to a connected device offline, reporting the outcome.

    The offline ``tempest deploy`` path: ensure the bundled host is installed,
    push the whole project once, launch, and exit — no Android SDK/NDK, Gradle,
    or ``android-host`` source tree. See :func:`deploy_offline`.

    Args:
        app: Path to the app file to deploy.
        force_install: Re-install the host APK even when already present.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid import __version__
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, deploy_offline

    console = Console(verbose=verbose)
    try:
        return deploy_offline(
            app,
            version=__version__,
            console=console,
            force_install=force_install,
        )
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
        console.fail(f"deploy failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_run(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    verbose: bool,
) -> int:
    """Build a shippable APK via Gradle, install + launch it, stream logs.

    The same Gradle build as ``tempest build`` (stamped with a unique
    ``applicationId``), then ``adb install`` + launch + ``logcat``. The launch
    component is ``<app_id>/org.tempestroid.host.MainActivity`` — the activity
    class lives in the fixed ``namespace`` while the package is the per-app id.

    Args:
        app: Path to the app file to bundle.
        app_id: The applicationId, or ``None`` to derive one from the project.
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The versionName.
        version_code: The versionCode.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import shutil
    import subprocess

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import connected_devices
    from tempestroid.cli.release_build import build_apk, derive_app_id, derive_app_name

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id or derive_app_id(project_name)
    resolved_name = app_name or derive_app_name(project_name)
    # The activity class lives in the fixed namespace; the package is the per-app
    # applicationId, so the launch component is <app_id>/<namespace>.MainActivity.
    host_activity = f"{resolved_id}/org.tempestroid.host.MainActivity"
    try:
        adb = shutil.which("adb")
        with console.step("Checking for a connected device"):
            if adb is None:
                raise StepError("adb not on PATH (install Android platform-tools)")
            devices = connected_devices()
            if not devices:
                raise StepError("no ready device (connect one and run `adb devices`)")
            joined = ", ".join(devices)
            console.info(f"device: {joined}")
        apk = build_apk(
            app,
            app_id=resolved_id,
            app_name=resolved_name,
            version_name=app_version,
            version_code=version_code,
            console=console,
        )
        with console.step(f"Installing {apk.name}"):
            console.run_command([adb, "install", "-r", str(apk)])
        with console.step(f"Launching {host_activity}"):
            console.run_command([adb, "shell", "am", "start", "-n", host_activity])
        console.info("running on device. Streaming logs (Ctrl-C to stop).")
        subprocess.run([adb, "logcat", "-v", "tag"], check=False)  # noqa: S603
        return 0
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"run failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_doctor(verbose: bool) -> int:
    """Probe the Android build/run prerequisites and report them.

    Args:
        verbose: Show resolution hints for failed checks.

    Returns:
        ``0`` when every prerequisite is satisfied, else ``1``.
    """
    from tempestroid.cli.console import Console
    from tempestroid.cli.packaging import preflight, report_preflight

    console = Console(verbose=verbose)
    console.info("tempest doctor — Android build/run prerequisites")
    ok = report_preflight(preflight(need_device=True), console)
    if ok:
        console.info("all prerequisites satisfied — ready to build and run.")
        return 0
    console.fail("some prerequisites are missing (see above).")
    return 1


def _run_setup(install: bool, sdk_dir: str | None, verbose: bool) -> int:
    """Diagnose (and optionally install) the Android build environment.

    Args:
        install: Auto-install the Android SDK + NDK when ``True``.
        sdk_dir: SDK directory to inspect/install into, or ``None`` for the
            default.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code (``0`` when build-ready).
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError
    from tempestroid.cli.setup_env import setup_build_env

    console = Console(verbose=verbose)
    try:
        return setup_build_env(
            sdk_dir=Path(sdk_dir) if sdk_dir else None,
            install=install,
            console=console,
        )
    except StepError:
        return 1
    except ToolchainError as exc:
        console.fail(f"setup failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"setup command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested command.

    Thin wrapper around the Typer ``app`` that returns a process exit code
    instead of raising :class:`SystemExit`, so it stays usable both as the
    console-script entry point and from tests. Click runs in standalone mode,
    so help/version output and usage errors are printed for us; we only map the
    resulting :class:`SystemExit` to a returned exit code.

    Args:
        argv: Argument vector to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    command = typer.main.get_command(app)
    try:
        command.main(args=argv, prog_name="tempest")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    app()
