"""Device transport over the hand-rolled JNI bridge (phase B3).

This is the Python half of the on-device bridge. It plugs a :class:`JniBridge`
(which ships serialized ``mount``/``patch`` messages to Kotlin) and an incoming
event sink (which feeds device taps/text back into the :class:`DeviceApp`) into
one asyncio loop.

The native module ``_tempest_host`` is provided by ``libtempest_host.so`` only
inside the Android app (it registers itself via ``PyImport_AppendInittab`` before
the interpreter boots). It is therefore imported **lazily**, so this module
imports cleanly on the desktop (where the framework is developed and tested) and
only requires the native side when :func:`run_device` actually runs.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from tempestroid.bridge.device import Bridge, DeviceApp
from tempestroid.core.state import App
from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX, resolve_native_result
from tempestroid.widgets import Widget

__all__ = ["JniBridge", "run_device", "run_device_file"]

S = TypeVar("S")


class _NativeHost(Protocol):
    """The surface ``_tempest_host`` exposes to Python (see ``tempest_host.c``)."""

    def send_to_host(self, message_json: str) -> None:
        """Hand a serialized message to Kotlin (Python → host)."""
        ...

    def set_event_sink(self, sink: Callable[[str, str], None]) -> None:
        """Register the callable the host invokes on a device event (host → Python)."""
        ...


def native_host() -> _NativeHost:
    """Import and return the native ``_tempest_host`` module.

    Returns:
        The native host module.

    Raises:
        RuntimeError: If imported off-device, where the module is absent.
    """
    try:
        import _tempest_host  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - desktop path
        raise RuntimeError(
            "_tempest_host is unavailable; run_device only works inside the "
            "Android host (libtempest_host.so registers the module)."
        ) from exc
    # The native module has no type stub; trust it implements the Protocol.
    return cast(_NativeHost, _tempest_host)


class JniBridge(Bridge):
    """A :class:`Bridge` that ships messages to Kotlin via the native host.

    Each message is JSON-encoded and handed to ``_tempest_host.send_to_host``,
    which marshals it across JNI to ``PythonRuntime.onMessageFromPython`` on the
    Kotlin side (the Compose renderer consumes it in phase B4).
    """

    def __init__(self) -> None:
        """Bind the bridge to the native host module."""
        self._host: _NativeHost = native_host()

    async def send(self, message: dict[str, Any]) -> None:
        """Serialize and ship one message to the host.

        Args:
            message: A JSON-able message dict (``mount`` / ``patch``).
        """
        self._host.send_to_host(json.dumps(message))


def run_device(state: S, view: Callable[[App[S]], Widget]) -> None:
    """Boot a :class:`DeviceApp` on a fresh asyncio loop and run it forever.

    This is the device-side analogue of ``run_qt``: it owns the loop, sends the
    initial ``mount`` over a :class:`JniBridge`, registers the native event sink
    (which marshals incoming device events back onto the loop), and blocks in
    ``run_forever``. Call it from the interpreter's main thread inside the host —
    the Kotlin side already runs the interpreter off the UI thread.

    Args:
        state: The initial application state.
        view: Builds the widget tree from the app.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    device: DeviceApp[S] = DeviceApp(state, view, JniBridge())

    def _on_event(token: str, payload_json: str) -> None:
        """Native callback: schedule an incoming event onto the loop.

        Invoked by the host from the UI thread (with the GIL held), so it only
        hands work to the loop via ``call_soon_threadsafe`` and returns fast.

        Args:
            token: The handler token addressed by the event.
            payload_json: The raw JSON payload (``""`` for none).
        """
        # A native callback must never raise back into JNI: a malformed payload
        # is dropped (logged) instead of crashing the host on the UI thread.
        try:
            payload: dict[str, Any] = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            _LOGGER.exception(
                "dropping event for token %r: invalid JSON payload", token
            )
            return
        # Native request/response results ride the same event channel under a
        # reserved token, so they need no extra JNI entry point. Route them to
        # the pending-future resolver instead of the widget handler registry.
        if token.startswith(NATIVE_RESULT_PREFIX):
            request_id = token[len(NATIVE_RESULT_PREFIX) :]
            loop.call_soon_threadsafe(resolve_native_result, request_id, payload)
            return
        message: dict[str, Any] = {
            "kind": "event",
            "token": token,
            "payload": payload,
        }
        loop.call_soon_threadsafe(
            lambda: loop.create_task(device.handle_event(message))
        )

    native_host().set_event_sink(_on_event)
    loop.create_task(device.start())
    loop.run_forever()


def run_device_file(path: str) -> None:
    """Load an app file (``make_state`` + ``view``) and run it on the device.

    The device entry point for an APK bundled by ``tempest build``: the user's
    app source is packaged as an asset, extracted to ``path`` on first launch,
    and run here. Mirrors :func:`run_device` but sources the state/view from a
    file via the same loader the dev cockpit and code-push client use.

    Args:
        path: Absolute path to the extracted app file on the device.
    """
    from pathlib import Path

    from tempestroid.cli.app_loader import spec_from_source

    source = Path(path).read_text(encoding="utf-8")
    spec = spec_from_source(source, filename=path)
    run_device(spec.make_state(), spec.view)
