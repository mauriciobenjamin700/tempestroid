"""Run a tempestroid app in the Qt simulator with an asyncio loop.

Fuses asyncio into Qt's event loop via ``qasync`` so the *same* loop drives Qt
widgets and Python coroutines: a button click can `await` (HTTPX, sleep, file
I/O) and, on completion, call ``app.set_state`` to schedule a coalesced rebuild —
all without freezing the UI, because the work runs as a loop task rather than
blocking the slot.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import TypeVar

import qasync  # pyright: ignore[reportMissingTypeStubs]
from PySide6.QtWidgets import QApplication

from tempestroid.core.state import App
from tempestroid.renderers.qt.renderer import QtRenderer
from tempestroid.widgets import Widget

__all__ = ["run_qt"]

S = TypeVar("S")


def run_qt(
    state: S,
    view: Callable[[App[S]], Widget],
    *,
    title: str = "tempestroid",
    size: tuple[int, int] = (360, 640),
) -> int:
    """Mount an app in a Qt window and run the fused Qt/asyncio loop.

    Args:
        state: The initial application state.
        view: Builds the widget tree from the app (reads ``app.state``, wires
            handlers that call ``app.set_state``).
        title: The window title.
        size: The initial window size as ``(width, height)``.

    Returns:
        The process exit code (``0`` on a clean loop shutdown).
    """
    qt_app = QApplication.instance() or QApplication(sys.argv)
    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    renderer = QtRenderer()
    app = App(state, view, apply_patches=renderer.apply)
    host = renderer.mount(app.start())
    host.setWindowTitle(title)
    host.resize(*size)
    host.show()

    with loop:
        loop.run_forever()
    return 0
