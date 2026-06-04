"""Native app-lifecycle stream (phase E8).

Like sensors, lifecycle is a *continuous* signal: the host pushes a
:class:`~tempestroid.widgets.events.LifecycleEvent` whenever the app moves
between foreground and background, over the existing event channel under the
reserved :data:`~tempestroid.bridge.protocol.LIFECYCLE_TOKEN`. The bridge routes
that token to :func:`dispatch_lifecycle_event`, which validates the payload and
fans it out to the callbacks registered via :func:`on_app_state_change`.

On the Qt simulator the lifecycle source is real: the app runner connects
``QApplication.applicationStateChanged`` and calls
:func:`dispatch_lifecycle_event` directly (no host round-trip), so
foreground/background tracking works on the desktop too.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tempestroid.widgets.events import LifecycleEvent

__all__ = [
    "LifecycleCallback",
    "on_app_state_change",
    "dispatch_lifecycle_event",
]

#: An app-state-change callback (sync or async).
LifecycleCallback = Callable[[LifecycleEvent], "Awaitable[None] | None"]

#: The registered lifecycle callbacks.
_lifecycle_callbacks: list[LifecycleCallback] = []


def on_app_state_change(callback: LifecycleCallback) -> Callable[[], None]:
    """Register a callback for app foreground/background transitions.

    Args:
        callback: Invoked with each :class:`LifecycleEvent` (sync or async).

    Returns:
        An ``unregister`` callable that removes this callback.
    """
    _lifecycle_callbacks.append(callback)

    def _unregister() -> None:
        """Remove this callback from the lifecycle registry."""
        if callback in _lifecycle_callbacks:
            _lifecycle_callbacks.remove(callback)

    return _unregister


def dispatch_lifecycle_event(payload: dict[str, Any]) -> None:
    """Dispatch an app-lifecycle change to the registered callbacks.

    Called on the loop thread by the bridge (device) or the Qt app runner
    (simulator) when the app state changes. The raw payload is validated into a
    :class:`LifecycleEvent` before fan-out; an async callback's coroutine is
    scheduled, a sync callback is called directly.

    Args:
        payload: The raw lifecycle payload (``{"state": ...}``).
    """
    import asyncio

    if not _lifecycle_callbacks:
        return
    event = LifecycleEvent.model_validate(payload)
    for callback in list(_lifecycle_callbacks):
        result = callback(event)
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)
