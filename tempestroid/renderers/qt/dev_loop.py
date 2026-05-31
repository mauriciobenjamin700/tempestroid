"""The ``tempest dev`` cockpit: simulator window + watcher + command loop.

Runs one fused Qt/asyncio loop that drives three things at once: the live
simulator window, a file watcher that hot-restarts on save, and a line-based
command loop on stdin (``r``/``R`` restart, ``s`` raise the window, ``q`` quit).

Saving the file (or pressing ``r``) **hot-reloads**: the view swaps in place and
state is preserved across the edit. ``R`` forces a **hot restart** (clean state).
A reload incompatible with the live state falls back to a clean restart, so the
loop never wedges. The device target (QR over LAN) arrives in track B; here it
shows as not connected.
"""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
from pathlib import Path
from typing import cast

import qasync  # pyright: ignore[reportMissingTypeStubs]
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.watcher import watch
from tempestroid.core.state import App
from tempestroid.devices import DEFAULT_DEVICE
from tempestroid.renderers.qt.app_runner import BackKeyFilter
from tempestroid.renderers.qt.simulator import Simulator

__all__ = ["run_dev"]

_BANNER = """\
tempest dev

  App         {app}
  Simulator   Qt          ● running
  Device      —           ○ not connected (use `tempest serve` for a device)

  Commands:
    r      hot reload  (preserve state)
    R      hot restart (clean state)
    s      raise the simulator window
    q      quit
"""


def _report_failure(exc: Exception, verbose: bool) -> None:
    """Print a reload/restart failure, with a full traceback in verbose mode.

    Args:
        exc: The exception raised while loading the app file.
        verbose: When ``True``, print the full traceback below the summary.
    """
    print(f"✗ reload failed: {type(exc).__name__}: {exc}")
    if verbose:
        traceback.print_exc()


def _restart(simulator: Simulator, path: Path, *, verbose: bool = False) -> None:
    """Reload the app file and hot-restart the simulator (clean state).

    A syntax or runtime error in the app file is printed and swallowed so the
    dev loop survives a bad save and recovers on the next one.

    Args:
        simulator: The simulator to restart.
        path: The app file path.
        verbose: Print the full traceback on a bad save.
    """
    started = time.monotonic()
    try:
        simulator.load(load_app_spec(path))
        print(f"↻ restarted from {path.name} (clean state, {_ms(started)})")
    except Exception as exc:  # noqa: BLE001 — keep the dev loop alive on bad saves
        _report_failure(exc, verbose)


def _reload(simulator: Simulator, path: Path, *, verbose: bool = False) -> None:
    """Reload the app file and hot-reload the simulator (preserve state).

    Mirrors :func:`_restart` but routes through :meth:`Simulator.reload`, which
    keeps the live state and falls back to a clean restart on an incompatible
    edit. Bad saves are printed and swallowed so the loop survives.

    Args:
        simulator: The simulator to reload.
        path: The app file path.
        verbose: Print the full traceback on a bad save.
    """
    started = time.monotonic()
    try:
        simulator.reload(load_app_spec(path))
        print(f"↻ reloaded from {path.name} (state preserved, {_ms(started)})")
    except Exception as exc:  # noqa: BLE001 — keep the dev loop alive on bad saves
        _report_failure(exc, verbose)


def _ms(started: float) -> str:
    """Format the elapsed time since ``started`` as a millisecond string.

    Args:
        started: A :func:`time.monotonic` timestamp taken before the work.

    Returns:
        A human-readable duration like ``"12ms"``.
    """
    return f"{(time.monotonic() - started) * 1000:.0f}ms"


def run_dev(path: str | Path, *, verbose: bool = False) -> int:
    """Run the dev cockpit for an app file until quit.

    Args:
        path: Path to the app's Python file.
        verbose: Print full tracebacks when a save fails to reload.

    Returns:
        The process exit code.
    """
    app_path = Path(path).resolve()
    qt_app = cast("QApplication", QApplication.instance() or QApplication(sys.argv))
    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    simulator = Simulator()
    _restart(simulator, app_path, verbose=verbose)  # first mount is a clean start

    def _current_app() -> App[object] | None:
        # Re-read each Esc press so a hot reload that swaps the app is honoured.
        try:
            return simulator.app
        except RuntimeError:
            return None

    back_filter = BackKeyFilter(_current_app)
    simulator.host.installEventFilter(back_filter)
    simulator.host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    simulator.host.setWindowTitle(f"tempestroid dev — {app_path.name}")
    simulator.host.resize(*DEFAULT_DEVICE.size)
    simulator.host.show()
    print(_BANNER.format(app=app_path))

    async def on_change() -> None:
        # save → preserve state (fall back to restart)
        _reload(simulator, app_path, verbose=verbose)

    def handle_command() -> None:
        line = sys.stdin.readline()
        if not line:  # EOF (stdin closed) → quit
            loop.stop()
            return
        command = line.strip()
        if command == "r":
            _reload(simulator, app_path, verbose=verbose)
        elif command == "R":
            _restart(simulator, app_path, verbose=verbose)
        elif command == "s":
            simulator.host.raise_()
            simulator.host.activateWindow()
        elif command == "q":
            loop.stop()

    watch_task = loop.create_task(watch([app_path], on_change))
    stdin_attached = sys.stdin.isatty() or not sys.stdin.closed
    if stdin_attached:
        loop.add_reader(sys.stdin.fileno(), handle_command)
    qt_app.lastWindowClosed.connect(loop.stop)

    try:
        with loop:
            loop.run_forever()
    finally:
        watch_task.cancel()
        if stdin_attached:
            try:
                loop.remove_reader(sys.stdin.fileno())
            except (ValueError, OSError):
                pass
    return 0
