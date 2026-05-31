"""LAN code-push dev client (phase B5, device side).

Runs inside the Android host: polls the dev server for source changes, and on
each change re-execs the app source and hot-restarts the :class:`DeviceApp` over
the bridge. This is the device end of the Expo-style loop — edit on the dev
machine, see it on the phone without rebuilding the APK.

:func:`run_dev_client` is transport-agnostic (bridge, sink registration and HTTP
fetch are injected) so it is testable on the desktop. :func:`serve_device` is the
thin device entry point that wires in the real JNI bridge + ``urllib`` fetch.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from tempestroid.bridge.device import Bridge, DeviceApp
from tempestroid.cli.app_loader import spec_from_source

__all__ = ["run_dev_client", "serve_device", "carry_state"]


def carry_state(old: object, new: object) -> None:
    """Copy attributes present on both ``old`` and ``new`` from old to new.

    Enables stateful hot reload: the freshly-built state keeps the running
    values for any field the edited app still declares. Fields the edit removed
    are dropped; fields it added keep their fresh defaults.

    Args:
        old: The previous app's state.
        new: The newly-built state to seed.
    """
    old_attrs = getattr(old, "__dict__", {})
    for key, value in old_attrs.items():
        if hasattr(new, key):
            try:
                setattr(new, key, value)
            except AttributeError:
                pass  # frozen/read-only field — leave the fresh default


async def run_dev_client(
    url: str,
    *,
    make_bridge: Callable[[], Bridge],
    register_sink: Callable[[Callable[[str, str], None]], None],
    fetch: Callable[[str], Awaitable[str]],
    poll_interval: float = 1.0,
    log: Callable[[str], None] = print,
    max_polls: int | None = None,
    preserve_state: bool = True,
) -> None:
    """Poll the dev server and hot-restart the app on every source change.

    Args:
        url: The dev server base URL (e.g. ``http://localhost:8765``).
        make_bridge: Factory for a fresh :class:`Bridge` per (re)load.
        register_sink: Registers the incoming-event callback with the transport
            (``_tempest_host.set_event_sink`` on device).
        fetch: Async ``url -> body`` HTTP GET.
        poll_interval: Seconds between version polls.
        log: Sink for status lines.
        max_polls: Stop after this many polls (tests); ``None`` runs forever.
        preserve_state: Carry matching state attributes across reloads (stateful
            hot reload). On a reload, attributes present on both the previous and
            the freshly-built state keep their previous values.
    """
    loop = asyncio.get_running_loop()
    current: dict[str, Any] = {"device": None, "hash": None}

    def on_event(token: str, payload_json: str) -> None:
        """Route a device event to the currently-loaded app."""
        device: DeviceApp[Any] | None = current["device"]
        if device is None:
            return
        payload: dict[str, Any] = json.loads(payload_json) if payload_json else {}
        message: dict[str, Any] = {"kind": "event", "token": token, "payload": payload}
        loop.call_soon_threadsafe(
            lambda: loop.create_task(device.handle_event(message))
        )

    register_sink(on_event)

    polls = 0
    while max_polls is None or polls < max_polls:
        polls += 1
        try:
            version = json.loads(await fetch(f"{url}/version")).get("hash")
            if version != current["hash"]:
                payload = json.loads(await fetch(f"{url}/app"))
                spec = spec_from_source(payload["source"], filename="<dev-push>")
                state = spec.make_state()
                previous: DeviceApp[Any] | None = current["device"]
                if preserve_state and previous is not None:
                    carry_state(previous.app.state, state)
                device = DeviceApp(state, spec.view, make_bridge())
                current["device"] = device
                current["hash"] = payload["hash"]
                await device.start()
                log(f"[tempest] pushed app {str(version)[:8]}")
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on any error
            log(f"[tempest] dev client error: {exc}")
        await asyncio.sleep(poll_interval)


def serve_device(url: str, *, poll_interval: float = 1.0) -> None:
    """Device entry point: run the code-push client over the real JNI bridge.

    Wires the native ``_tempest_host`` sink, an ``urllib`` fetch, and the
    :class:`JniBridge`, then runs :func:`run_dev_client` forever on a fresh loop.

    Args:
        url: The dev server base URL reachable from the device (with
            ``adb reverse tcp:8765 tcp:8765`` this is ``http://localhost:8765``).
        poll_interval: Seconds between version polls.
    """
    import urllib.request

    from tempestroid.bridge.jni import JniBridge, native_host

    host = native_host()

    async def _fetch(target: str) -> str:
        """Fetch a URL body off the event loop thread."""

        def _get() -> str:
            with urllib.request.urlopen(target, timeout=5) as response:  # noqa: S310
                return response.read().decode("utf-8")

        return await asyncio.to_thread(_get)

    asyncio.run(
        run_dev_client(
            url,
            make_bridge=JniBridge,
            register_sink=host.set_event_sink,
            fetch=_fetch,
            poll_interval=poll_interval,
        )
    )
