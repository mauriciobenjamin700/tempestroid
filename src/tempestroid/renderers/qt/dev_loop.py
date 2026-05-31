"""The ``tempest dev`` cockpit: simulator window + watcher + command loop.

Runs one fused Qt/asyncio loop that drives three things at once: the live
simulator window, a file watcher that hot-restarts on save, and a line-based
command loop on stdin (``r``/``R`` restart, ``s`` raise the window, ``q`` quit).

v1 is **hot restart only** (clean state) — robust and simple; stateful hot reload
is a post-v1 refinement. The device target (QR over LAN) arrives in track B; here
it shows as not connected.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import cast

import qasync  # pyright: ignore[reportMissingTypeStubs]
from PySide6.QtWidgets import QApplication

from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.watcher import watch
from tempestroid.renderers.qt.simulator import Simulator

__all__ = ["run_dev"]

_BANNER = """\
tempest dev

  Simulator   Qt          ● running
  Device      —           ○ not connected (phase B)

  Commands:
    r / R  hot restart (clean state)
    s      raise the simulator window
    q      quit
"""


def _restart(simulator: Simulator, path: Path) -> None:
    """Reload the app file and hot-restart the simulator, reporting errors.

    A syntax or runtime error in the app file is printed and swallowed so the
    dev loop survives a bad save and recovers on the next one.

    Args:
        simulator: The simulator to restart.
        path: The app file path.
    """
    try:
        simulator.load(load_app_spec(path))
        print(f"↻ restarted from {path}")
    except Exception as exc:  # noqa: BLE001 — keep the dev loop alive on bad saves
        print(f"✗ reload failed: {type(exc).__name__}: {exc}")


def run_dev(path: str | Path) -> int:
    """Run the dev cockpit for an app file until quit.

    Args:
        path: Path to the app's Python file.

    Returns:
        The process exit code.
    """
    app_path = Path(path).resolve()
    qt_app = cast("QApplication", QApplication.instance() or QApplication(sys.argv))
    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    simulator = Simulator()
    _restart(simulator, app_path)
    simulator.host.setWindowTitle(f"tempestroid dev — {app_path.name}")
    simulator.host.resize(360, 640)
    simulator.host.show()
    print(_BANNER)

    async def on_change() -> None:
        _restart(simulator, app_path)

    def handle_command() -> None:
        line = sys.stdin.readline()
        if not line:  # EOF (stdin closed) → quit
            loop.stop()
            return
        command = line.strip()
        if command in ("r", "R"):
            _restart(simulator, app_path)
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
