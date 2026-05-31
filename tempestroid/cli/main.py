"""``tempest`` command-line entry point.

``tempest dev`` runs the interactive simulator cockpit (phase A5). ``tempest
serve`` pushes an app to a device over LAN (phase B5). The phase-C packaging
commands — ``new`` (scaffold), ``build`` (APK), ``run`` (install + logcat) —
drive the ``android-host`` Gradle project and ``adb``. Qt is imported lazily
inside ``dev`` so ``tempest --help`` works without the optional ``qt`` extra.
"""

from __future__ import annotations

import argparse
import sys

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured parser with all ``tempest`` subcommands registered.
    """
    # Imported lazily to avoid a circular import: the dev-server client imports
    # this CLI package, and the top-level package imports the dev server.
    from tempestroid import __version__

    parser = argparse.ArgumentParser(
        prog="tempest",
        description="Build native Android apps in typed Python.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    dev = subparsers.add_parser("dev", help="Run the simulator dev loop.")
    dev.add_argument("app", help="Path to the app file (e.g. examples/counter/app.py).")
    serve = subparsers.add_parser(
        "serve", help="Serve an app to a device over LAN (code-push + log relay)."
    )
    serve.add_argument("app", help="Path to the app file to push to the device.")
    serve.add_argument(
        "--port", type=int, default=8765, help="TCP port (default: 8765)."
    )
    serve.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)."
    )
    subparsers.add_parser(
        "spec", help="Print the typed contract (widgets/events) as JSON."
    )
    new = subparsers.add_parser("new", help="Scaffold a new tempestroid app.")
    new.add_argument("name", help="Project name (also the directory name).")
    new.add_argument(
        "--into", default=".", help="Parent directory for the project (default: .)."
    )
    build = subparsers.add_parser("build", help="Build an APK bundling an app.")
    build.add_argument("app", help="Path to the app file to bundle into the APK.")
    build.add_argument(
        "--release", action="store_true", help="Build the release variant."
    )
    run = subparsers.add_parser(
        "run", help="Build, install on a device, and stream logs."
    )
    run.add_argument("app", help="Path to the app file to bundle into the APK.")
    run.add_argument(
        "--release", action="store_true", help="Build the release variant."
    )
    return parser


def _run_dev(app: str) -> int:
    """Dispatch to the Qt dev cockpit, importing Qt lazily.

    Args:
        app: Path to the app file.

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
    return run_dev(app)


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


def _run_serve(app: str, host: str, port: int) -> int:
    """Serve an app to a device and relay its logs until interrupted.

    Args:
        app: Path to the app file.
        host: Bind address.
        port: TCP port.

    Returns:
        The process exit code.
    """
    import threading

    from tempestroid.devserver import DevServer, render_qr

    server = DevServer(app, host=host, port=port)
    try:
        server.start()
    except OSError as exc:
        print(f"could not start dev server on {host}:{port}: {exc}")
        return 1

    lan_url = f"http://{_lan_ip()}:{server.port}"
    print(render_qr(lan_url))
    print(
        f"tempest dev server on port {server.port}.\n"
        f"  LAN:  {lan_url}\n"
        f"  USB:  adb reverse tcp:{server.port} tcp:{server.port} "
        f"→ http://localhost:{server.port}\n"
        "Edit + save the app file to hot-restart on device. Ctrl-C to stop."
    )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopping dev server.")
    finally:
        server.stop()
    return 0


def _run_new(name: str, into: str) -> int:
    """Scaffold a new app project, reporting the outcome.

    Args:
        name: The project name (and directory name).
        into: Parent directory to create the project under.

    Returns:
        The process exit code.
    """
    from tempestroid.cli.scaffold import scaffold

    try:
        root = scaffold(name, parent=into)
    except (ValueError, FileExistsError) as exc:
        print(f"cannot scaffold: {exc}")
        return 1
    print(
        f"created {root}\n"
        f"  uv run tempest dev {root.name}/app.py     # simulator + hot reload\n"
        f"  uv run tempest serve {root.name}/app.py   # push to a device over LAN"
    )
    return 0


def _run_build(app: str, release: bool) -> int:
    """Build an APK bundling the given app, reporting the outcome.

    Args:
        app: Path to the app file to bundle.
        release: Whether to build the release variant.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid.cli.packaging import ToolchainError, build_apk

    try:
        apk = build_apk(app, release=release)
    except (ToolchainError, FileNotFoundError) as exc:
        print(f"build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"gradle build failed (exit {exc.returncode}).")
        return exc.returncode or 1
    print(f"built {apk}")
    return 0


def _run_run(app: str, release: bool) -> int:
    """Build, install on a device, and stream logs, reporting the outcome.

    Args:
        app: Path to the app file to bundle.
        release: Whether to build the release variant.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid.cli.packaging import ToolchainError, run_on_device

    try:
        return run_on_device(app, release=release)
    except (ToolchainError, FileNotFoundError) as exc:
        print(f"run failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested command.

    Args:
        argv: Argument vector to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    command: str | None = args.command
    if command is None:
        parser.print_help()
        return 0
    if command == "dev":
        return _run_dev(args.app)
    if command == "serve":
        return _run_serve(args.app, args.host, args.port)
    if command == "spec":
        import json

        from tempestroid import introspect

        print(json.dumps(introspect(), indent=2))
        return 0
    if command == "new":
        return _run_new(args.name, args.into)
    if command == "build":
        return _run_build(args.app, args.release)
    if command == "run":
        return _run_run(args.app, args.release)
    parser.error(f"unknown command: {command}")


if __name__ == "__main__":
    sys.exit(main())
