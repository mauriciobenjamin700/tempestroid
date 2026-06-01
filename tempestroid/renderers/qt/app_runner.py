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
from typing import Any, TypeVar

import qasync  # pyright: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from tempestroid.core.state import App
from tempestroid.devices import DEFAULT_DEVICE
from tempestroid.renderers.qt.renderer import QtRenderer
from tempestroid.widgets import Widget

__all__ = ["run_qt", "BackKeyFilter"]

S = TypeVar("S")


class BackKeyFilter(QObject):
    """Maps the simulator's ``Esc`` key to the Android back button (``app.pop``).

    Installed on the renderer's host widget, it intercepts ``Esc`` key presses and
    routes them to a current-:class:`App` provider's :meth:`App.pop`, mirroring the
    hardware/gesture back navigation a device performs. At the root (``can_pop``
    is ``False``) :meth:`App.pop` is a no-op, so ``Esc`` is swallowed but the
    event still propagates (the simulator does not close on a root back, matching
    the device which leaves the default back action to the host).
    """

    def __init__(self, current_app: Callable[[], App[Any] | None]) -> None:
        """Initialize the filter.

        Args:
            current_app: Returns the app to pop (re-read on each key press so a
                hot reload that swaps the app is honoured), or ``None`` if none.
        """
        super().__init__()
        self._current_app: Callable[[], App[Any] | None] = current_app

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept ``Esc`` key presses and route them to ``app.pop``.

        Args:
            watched: The object the event targets (the host widget).
            event: The Qt event.

        Returns:
            ``True`` when an ``Esc`` press popped a route (consumed); otherwise
            the base-class result (event continues to propagate).
        """
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast_key(event)
            if key_event is not None and key_event.key() == Qt.Key.Key_Escape:
                app = self._current_app()
                if app is not None:
                    app.pop()
                return True
        return super().eventFilter(watched, event)


def cast_key(event: QEvent) -> QKeyEvent | None:
    """Return ``event`` as a :class:`QKeyEvent` when it is one, else ``None``.

    Args:
        event: The Qt event to narrow.

    Returns:
        The key event, or ``None`` if ``event`` is not a key event.
    """
    return event if isinstance(event, QKeyEvent) else None


def run_qt(
    state: S,
    view: Callable[[App[S]], Widget],
    *,
    title: str = "tempestroid",
    size: tuple[int, int] = DEFAULT_DEVICE.size,
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
    # Esc → back (app.pop), mirroring the device back button. The filter is kept
    # alive on the host so Qt does not GC it (it does not take ownership).
    back_filter = BackKeyFilter(lambda: app)
    host.installEventFilter(back_filter)
    host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    host._tempest_back_filter = back_filter  # type: ignore[attr-defined]
    host.setWindowTitle(title)
    host.resize(*size)
    host.show()

    with loop:
        loop.run_forever()
    return 0
