"""Native connectivity capability (phase E8).

Mixed-shape module: :func:`get_connectivity` is a one-shot request/response read
of the current network state, while :func:`on_connectivity_change` opens a
*stream* — the host pushes a
:class:`~tempestroid.widgets.events.ConnectivityEvent` over the existing event
channel under the reserved token ``"__connectivity__:<state>"`` whenever the
network changes. The bridge routes that token to
:func:`dispatch_connectivity_event`, which validates the payload and fans it out
to the registered callbacks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tempestroid.native.dispatch import send_native, send_native_request
from tempestroid.widgets.events import ConnectivityEvent, ConnectivityState

__all__ = [
    "ConnectivityCallback",
    "get_connectivity",
    "on_connectivity_change",
    "dispatch_connectivity_event",
]

#: A connectivity-change callback (sync or async).
ConnectivityCallback = Callable[[ConnectivityEvent], "Awaitable[None] | None"]

#: The registered connectivity callbacks.
_connectivity_callbacks: list[ConnectivityCallback] = []


async def get_connectivity() -> ConnectivityState:
    """Read the device's current network connectivity state.

    Returns:
        The current :class:`ConnectivityState`.

    Raises:
        RuntimeError: If called off-device.
    """
    data = await send_native_request("connectivity", "get", {})
    return ConnectivityState(str(data.get("state", ConnectivityState.DISCONNECTED)))


def on_connectivity_change(callback: ConnectivityCallback) -> Callable[[], None]:
    """Register a callback for network connectivity changes.

    Opens the host connectivity stream (idempotent on the host) and registers
    ``callback`` to receive each :class:`ConnectivityEvent`.

    Args:
        callback: Invoked with each connectivity change (sync or async).

    Returns:
        An ``unregister`` callable that removes this callback and stops the host
        stream once no callbacks remain.

    Raises:
        RuntimeError: If called off-device.
    """
    _connectivity_callbacks.append(callback)
    send_native("connectivity", "start", {})

    def _unregister() -> None:
        """Remove this callback and stop the stream when it was the last."""
        if callback in _connectivity_callbacks:
            _connectivity_callbacks.remove(callback)
            if not _connectivity_callbacks:
                send_native("connectivity", "stop", {})

    return _unregister


def dispatch_connectivity_event(payload: dict[str, Any]) -> None:
    """Dispatch a host connectivity change to the registered callbacks.

    Called on the loop thread by the bridge when a ``"__connectivity__:<state>"``
    token arrives. The raw payload is validated into a :class:`ConnectivityEvent`
    before fan-out; an async callback's coroutine is scheduled, a sync callback
    is called directly.

    Args:
        payload: The raw connectivity payload (``{"state": ...}``).
    """
    import asyncio

    if not _connectivity_callbacks:
        return
    event = ConnectivityEvent.model_validate(payload)
    for callback in list(_connectivity_callbacks):
        result = callback(event)
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)
