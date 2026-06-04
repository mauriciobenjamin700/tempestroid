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
from tempestroid.bridge.protocol import (
    BACK_TOKEN,
    CONNECTIVITY_TOKEN_PREFIX,
    LIFECYCLE_TOKEN,
    SENSOR_TOKEN_PREFIX,
)
from tempestroid.cli.app_loader import spec_from_source
from tempestroid.native.connectivity import dispatch_connectivity_event
from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX, resolve_native_result
from tempestroid.native.lifecycle import dispatch_lifecycle_event
from tempestroid.native.sensors import dispatch_sensor_event

__all__ = ["run_dev_client", "serve_device"]


async def run_dev_client(
    url: str,
    *,
    make_bridge: Callable[[], Bridge],
    register_sink: Callable[[Callable[[str, str], None]], None],
    fetch: Callable[[str], Awaitable[str]],
    poll_interval: float = 1.0,
    log: Callable[[str], None] = print,
    max_polls: int | None = None,
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
    """
    loop = asyncio.get_running_loop()
    current: dict[str, Any] = {"device": None, "hash": None}

    def on_event(token: str, payload_json: str) -> None:
        """Route a device event to the currently-loaded app.

        Native request/response results ride the same event channel under a
        reserved token (see :data:`NATIVE_RESULT_PREFIX`); route those to the
        pending-future resolver so ``async`` capability calls (geolocation,
        camera, storage, clipboard, bluetooth) resolve under code-push too —
        mirroring :func:`tempestroid.bridge.jni.run_device`.
        """
        payload: dict[str, Any] = json.loads(payload_json) if payload_json else {}
        # A system back action (Android back) rides the same event channel under
        # the reserved BACK_TOKEN — route it straight to App.pop, mirroring
        # tempestroid.bridge.jni.run_device. Without this the code-push path drops
        # the back event (no widget handler matches), so the device back button
        # would not pop under ``tempest serve`` even though the bundled app does.
        if token == BACK_TOKEN:
            back_device: DeviceApp[Any] | None = current["device"]
            if back_device is not None:
                loop.call_soon_threadsafe(back_device.app.pop)
            return
        if token.startswith(NATIVE_RESULT_PREFIX):
            request_id = token[len(NATIVE_RESULT_PREFIX) :]
            loop.call_soon_threadsafe(resolve_native_result, request_id, payload)
            return
        # Reserved stream tokens (sensor samples, lifecycle transitions,
        # connectivity changes) ride the same event channel and must be routed
        # here too — without this the ``tempest serve`` code-push path would
        # silently drop them (the lesson from E0d, where the dev client forgot
        # the reserved tokens). Mirrors tempestroid.bridge.jni.make_event_sink.
        sensor_prefix = f"{SENSOR_TOKEN_PREFIX}:"
        if token.startswith(sensor_prefix):
            sensor_type = token[len(sensor_prefix) :]
            loop.call_soon_threadsafe(dispatch_sensor_event, sensor_type, payload)
            return
        if token == LIFECYCLE_TOKEN:
            loop.call_soon_threadsafe(dispatch_lifecycle_event, payload)
            return
        if token.startswith(f"{CONNECTIVITY_TOKEN_PREFIX}:"):
            loop.call_soon_threadsafe(dispatch_connectivity_event, payload)
            return
        device: DeviceApp[Any] | None = current["device"]
        if device is None:
            return
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
                device: DeviceApp[Any] | None = current["device"]
                short = str(version)[:8]
                if device is None:
                    device = DeviceApp(spec.make_state(), spec.view, make_bridge())
                    current["device"] = device
                    await device.start()
                    log(f"[tempest] pushed app {short}")
                else:
                    # Hot-reload preserving on-device state; if the new view is
                    # incompatible with the live state, restart clean.
                    try:
                        device.reload(spec.view)
                        log(f"[tempest] hot-reloaded {short} (state preserved)")
                    except Exception as reload_exc:  # noqa: BLE001
                        device = DeviceApp(
                            spec.make_state(), spec.view, make_bridge()
                        )
                        current["device"] = device
                        await device.start()
                        log(
                            f"[tempest] hot-restarted {short} "
                            f"(state reset: {reload_exc})"
                        )
                current["hash"] = payload["hash"]
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
