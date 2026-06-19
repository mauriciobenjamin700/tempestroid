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
from tempest_core.core.ir import Patch
from tempest_core.core.state import App
from tempest_core.devices import DEFAULT_DEVICE, Device
from tempest_core.theme import Theme
from tempest_core.widgets import AppState, Widget

from tempestroid.native.lifecycle import dispatch_lifecycle_event
from tempestroid.renderers.qt.platform_setup import configure_qt_platform
from tempestroid.renderers.qt.renderer import QtRenderer

__all__ = ["run_qt", "BackKeyFilter", "connect_lifecycle"]

S = TypeVar("S")

#: Maps each Qt ``ApplicationState`` to the framework :class:`AppState` the
#: lifecycle stream reports. ``ApplicationActive`` (window focused/foreground) →
#: ``FOREGROUND``; ``ApplicationSuspended``/``ApplicationHidden`` (no visible,
#: usable window) → ``BACKGROUND``; ``ApplicationInactive`` (transitioning,
#: partially obscured) → ``INACTIVE``.
_QT_APP_STATE: dict[Qt.ApplicationState, AppState] = {
    Qt.ApplicationState.ApplicationActive: AppState.FOREGROUND,
    Qt.ApplicationState.ApplicationInactive: AppState.INACTIVE,
    Qt.ApplicationState.ApplicationSuspended: AppState.BACKGROUND,
    Qt.ApplicationState.ApplicationHidden: AppState.BACKGROUND,
}


def connect_lifecycle(qt_app: QApplication) -> None:
    """Wire Qt's application-state changes into the lifecycle stream.

    Connects ``QApplication.applicationStateChanged`` to
    :func:`~tempestroid.native.lifecycle.dispatch_lifecycle_event`, translating
    each Qt :class:`Qt.ApplicationState` into the framework
    :class:`~tempestroid.widgets.AppState`. This is the desktop analogue of the
    device's ``__lifecycle__`` token: a window losing/gaining focus drives the
    same ``on_app_state_change`` callbacks an app registers, so foreground/
    background tracking works in the simulator without a host round-trip.

    Args:
        qt_app: The running ``QApplication`` whose state changes to observe.
    """

    def _on_state_changed(state: Qt.ApplicationState) -> None:
        """Forward a Qt application-state change to the lifecycle dispatch.

        Args:
            state: The new Qt application state.
        """
        app_state = _QT_APP_STATE.get(state)
        if app_state is not None:
            dispatch_lifecycle_event({"state": app_state.value})

    qt_app.applicationStateChanged.connect(_on_state_changed)


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


def _apply_with_context(renderer: QtRenderer) -> Callable[[list[Patch]], None]:
    """Build the app's ``apply_patches`` callback: apply, then sync context.

    Wraps :meth:`QtRenderer.apply` so that after every coalesced patch batch the
    renderer re-reads the app's theme/locale context. ``set_theme`` /
    ``set_locale`` only mutate the app and request a rebuild; the resulting empty
    or non-empty patch batch flows here, and ``sync_context`` swaps the palette /
    layout direction to match — keeping the visual theme in lockstep with the
    declarative ``app.theme`` / ``app.locale`` without a dedicated callback.

    Args:
        renderer: The renderer whose patches to apply and context to sync.

    Returns:
        The ``apply_patches`` callback to hand to :class:`App`.
    """

    def _apply(patches: list[Patch]) -> None:
        """Apply ``patches`` then re-sync the renderer's theme/locale context.

        Args:
            patches: The coalesced patch batch from the reconciler.
        """
        renderer.apply(patches)
        renderer.sync_context()

    return _apply


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
    device: Device | None = None,
    theme: Theme | None = None,
) -> int:
    """Mount an app in a Qt window and run the fused Qt/asyncio loop.

    Args:
        state: The initial application state.
        view: Builds the widget tree from the app (reads ``app.state``, wires
            handlers that call ``app.set_state``).
        title: The window title.
        size: The initial window size as ``(width, height)``. Used when no
            ``device`` is given (kept for backward compatibility).
        device: An optional :class:`~tempestroid.devices.Device` preset to size
            the simulator window to that device's logical viewport. When given it
            **wins over** ``size`` (the window resizes to ``device.size``), so a
            caller pinning a real device's viewport overrides the raw tuple.
        theme: The app's initial :class:`~tempest_core.Theme` (e.g. a dark theme).
            ``None`` inherits the platform theme. The renderer reads ``app.theme``
            for its palette, so a dark theme paints the simulator dark.

    Returns:
        The process exit code (``0`` on a clean loop shutdown).
    """
    window_size = device.size if device is not None else size
    # Prefer xcb + mute the qpa probe on Linux/WSLg before the QApplication is
    # created (no-op when the user pinned QT_QPA_PLATFORM/QT_LOGGING_RULES — so
    # `QT_QPA_PLATFORM=offscreen` in headless tests is left untouched).
    configure_qt_platform()
    qt_app = QApplication.instance() or QApplication(sys.argv)
    if isinstance(qt_app, QApplication):
        connect_lifecycle(qt_app)
    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    renderer = QtRenderer()
    # Drive the animation frame clock off the fused qasync loop's monotonic clock
    # so ``App._tick`` computes each frame's ``dt`` from the same time base the
    # ``loop.call_later(1/60)`` scheduling uses. After each rebuild the renderer
    # re-reads the app's theme/locale context (``sync_context``) so a
    # ``set_theme``/``set_locale`` — which only schedules a rebuild — takes visual
    # effect (palette swap + layout direction).
    app: App[S] = App(
        state,
        view,
        apply_patches=_apply_with_context(renderer),
        time_source=loop.time,
        theme=theme,
    )
    # The app builds a `Scene` (root tree + floating overlay layer). The Qt
    # renderer mounts both; a host-owned overlay dismissal (dialog close, menu
    # select, scrim tap) is routed back to `App.dismiss` — the desktop analogue
    # of the device bridge's `__dismiss__:<id>` token.
    renderer.set_dismiss_overlay(app.dismiss)
    # Wire the live app so the renderer reads theme (palette), locale (RTL) and
    # forwards resize events to ``App._update_media`` (E9 transversal context).
    renderer.set_app(app)
    host = renderer.mount(app.start())
    # Esc → back (app.pop), mirroring the device back button. The filter is kept
    # alive on the host so Qt does not GC it (it does not take ownership).
    back_filter = BackKeyFilter(lambda: app)
    host.installEventFilter(back_filter)
    host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    host._tempest_back_filter = back_filter  # type: ignore[attr-defined]
    host.setWindowTitle(title)
    host.resize(*window_size)
    host.show()

    with loop:
        loop.run_forever()
    return 0
