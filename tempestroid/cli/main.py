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
    release: Annotated[
        bool,
        typer.Option("--release", help="Build the release variant."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full Gradle/adb output.",
        ),
    ] = False,
) -> None:
    """Build a standalone, shippable APK with the whole project baked in.

    Bundles the app's entire project tree (multi-file imports included) into the
    host and drives Gradle to produce a self-contained `.apk` you can hand to
    anyone — it runs the app with no dev server. Needs the Android SDK/NDK + an
    `android-host` checkout. For a fast no-toolchain run on your own connected
    device, use `tempest deploy`; for a hot-reload loop, `tempest serve`.
    """
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_build(resolved, release, verbose))


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
    release: Annotated[
        bool,
        typer.Option("--release", help="Build the release variant."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full Gradle/adb output.",
        ),
    ] = False,
) -> None:
    """Build, install on a device, and stream logs."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_run(resolved, release, verbose))


@app.command("doctor")
def doctor_cmd(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show resolution hints."),
    ] = False,
) -> None:
    """Check the Android build/run prerequisites and exit."""
    raise typer.Exit(_run_doctor(verbose))


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


def _run_build(app: str, release: bool, verbose: bool) -> int:
    """Build a standalone shippable APK bundling the project, reporting outcome.

    Bundles the whole project tree and drives Gradle to produce a self-contained
    `.apk` (needs the Android SDK/NDK + an ``android-host`` checkout). See
    :func:`build_apk` / :func:`stage_app_bundle`.

    Args:
        app: Path to the app's entry file to bundle.
        release: Whether to build the release variant.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, build_apk

    console = Console(verbose=verbose)
    try:
        build_apk(app, release=release, console=console)
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
        console.fail(f"build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"gradle build failed (exit {exc.returncode}).")
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


def _run_run(app: str, release: bool, verbose: bool) -> int:
    """Build, install on a device, and stream logs, reporting the outcome.

    Args:
        app: Path to the app file to bundle.
        release: Whether to build the release variant.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, run_on_device

    console = Console(verbose=verbose)
    try:
        return run_on_device(app, release=release, console=console)
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
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
