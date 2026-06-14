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
import shutil
import sys
import tempfile
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tempestroid.bridge.device import Bridge, DeviceApp
from tempestroid.bridge.errors import error_screen
from tempestroid.bridge.protocol import (
    BACK_TOKEN,
    BACKGROUND_TOKEN_PREFIX,
    CONNECTIVITY_TOKEN_PREFIX,
    LIFECYCLE_TOKEN,
    SENSOR_TOKEN_PREFIX,
)
from tempestroid.cli.app_loader import spec_from_project
from tempestroid.cli.bundle import extract_bundle
from tempestroid.native.background import dispatch_background_task
from tempestroid.native.connectivity import dispatch_connectivity_event
from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX, resolve_native_result
from tempestroid.native.lifecycle import dispatch_lifecycle_event
from tempestroid.native.sensors import dispatch_sensor_event

__all__ = ["run_dev_client", "serve_device"]

_BUNDLE_PREFIX = "tempest-app-"


def _sweep_stale_bundles(keep: Path | None = None) -> int:
    """Delete leftover code-push bundle dirs from earlier ``serve`` sessions.

    Each ``tempest serve`` push extracts the project to a fresh
    ``tempest-app-*`` temp dir (see :func:`_load_bundle_spec`). Within a single
    client process the previous push's dir is removed on the next push, but a
    *new* process (every ``serve`` invocation is one) starts with no prior root
    and never reclaims the dirs the earlier processes left behind. Across many
    pushes — e.g. validating the whole example gallery — those orphans pile up
    and fill the device/emulator ``/data`` partition, which then surfaces as a
    bogus extraction failure (error screen) on a perfectly good app.

    Sweeping the temp dir once at client startup reclaims that space. It is
    best-effort: any dir that cannot be removed (in use, permission) is skipped.

    Args:
        keep: A bundle root to preserve (the current process's own), if any.

    Returns:
        The number of stale bundle dirs removed.
    """
    tmp_root = Path(tempfile.gettempdir())
    removed = 0
    for path in tmp_root.glob(f"{_BUNDLE_PREFIX}*"):
        if not path.is_dir() or (keep is not None and path == keep):
            continue
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            removed += 1
    return removed


def _load_bundle_spec(data: bytes, previous_root: Path | None) -> tuple[Any, Path]:
    """Extract a pushed bundle, swap it onto ``sys.path``, and load its spec.

    Removes the previous push's root from ``sys.path`` (and disk) so a re-push
    cannot leak stale modules, extracts the new bundle to a fresh temp dir, and
    loads the entry via :func:`spec_from_project` (which adds the new root).

    Args:
        data: The bundle ``.zip`` bytes fetched from ``/bundle``.
        previous_root: The prior push's extraction root, or ``None`` on first
            push.

    Returns:
        A ``(spec, root)`` pair — the loaded :class:`AppSpec` and its new root.
    """
    if previous_root is not None:
        root_str = str(previous_root)
        while root_str in sys.path:
            sys.path.remove(root_str)
        shutil.rmtree(previous_root, ignore_errors=True)
    dest = Path(tempfile.mkdtemp(prefix="tempest-app-"))
    layout = extract_bundle(data, dest)
    spec = spec_from_project(layout.root, layout.entry)
    return spec, layout.root


async def run_dev_client(
    url: str,
    *,
    make_bridge: Callable[[], Bridge],
    register_sink: Callable[[Callable[[str, str], None]], None],
    fetch: Callable[[str], Awaitable[bytes]],
    poll_interval: float = 1.0,
    log: Callable[[str], None] = print,
    max_polls: int | None = None,
) -> None:
    """Poll the dev server and hot-restart the app on every project change.

    Args:
        url: The dev server base URL (e.g. ``http://localhost:8765``).
        make_bridge: Factory for a fresh :class:`Bridge` per (re)load.
        register_sink: Registers the incoming-event callback with the transport
            (``_tempest_host.set_event_sink`` on device).
        fetch: Async ``url -> body`` HTTP GET returning raw bytes (``/version``
            is JSON, ``/bundle`` is the project zip).
        poll_interval: Seconds between version polls.
        log: Sink for status lines.
        max_polls: Stop after this many polls (tests); ``None`` runs forever.
    """
    loop = asyncio.get_running_loop()
    current: dict[str, Any] = {"device": None, "hash": None, "root": None}

    # Reclaim disk left by earlier ``serve`` sessions before the first push, so
    # a long run (e.g. the whole example gallery) cannot fill ``/data`` with
    # orphaned bundle dirs and fail a good app with a bogus extraction error.
    swept = _sweep_stale_bundles()
    if swept:
        log(f"[tempest] swept {swept} stale bundle dir(s)")

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
        background_prefix = f"{BACKGROUND_TOKEN_PREFIX}:"
        if token.startswith(background_prefix):
            loop.call_soon_threadsafe(
                dispatch_background_task, token[len(background_prefix) :]
            )
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
            # Network zone: a transient fetch failure (timeout, reset) must NOT
            # commit the hash, so the next poll retries the same version.
            version = json.loads((await fetch(f"{url}/version")).decode("utf-8")).get(
                "hash"
            )
            if version != current["hash"]:
                data = await fetch(f"{url}/bundle")
                # App zone: from here the bundle is in hand. Commit the hash up
                # front so a *broken* app (load/build error) is not re-fetched on
                # every poll — we wait for the next edit. The error is surfaced
                # on-device as a red error screen instead of a blank window.
                current["hash"] = version
                await _apply_push(data, current, make_bridge, log)
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on any error
            log(f"[tempest] dev client error: {exc}")
        await asyncio.sleep(poll_interval)


async def _apply_push(
    data: bytes,
    current: dict[str, Any],
    make_bridge: Callable[[], Bridge],
    log: Callable[[str], None],
) -> None:
    """Load a freshly-fetched bundle and (re)start or hot-reload the app.

    A load/build failure is caught and mounted as an on-device error screen (the
    device analogue of the desktop dev loop printing a caught exception) rather
    than left as a blank window — the developer sees *what* broke without
    attaching ``adb``. The poll loop keeps running, so the next saved edit
    recovers.

    Args:
        data: The bundle ``.zip`` bytes fetched from ``/bundle``.
        current: The mutable load state (``device``/``root``) shared with the
            poll loop.
        make_bridge: Factory for a fresh :class:`Bridge` per (re)load.
        log: Sink for status lines.
    """
    try:
        spec, root = _load_bundle_spec(data, current["root"])
        current["root"] = root
    except Exception:  # noqa: BLE001 - surface any load failure on-device
        await _mount_error(current, make_bridge, log, traceback.format_exc())
        return
    device: DeviceApp[Any] | None = current["device"]
    is_error = bool(current.get("error"))
    if device is None or is_error:
        # First push, or replacing an error screen: start clean.
        try:
            device = DeviceApp(spec.make_state(), spec.view, make_bridge())
            current["device"] = device
            current["error"] = False
            await device.start()
            log("[tempest] pushed app")
        except Exception:  # noqa: BLE001 - a first-build error is still on-device
            await _mount_error(current, make_bridge, log, traceback.format_exc())
        return
    # Hot-reload preserving on-device state; if the new view is incompatible
    # with the live state, restart clean.
    try:
        device.reload(spec.view)
        log("[tempest] hot-reloaded (state preserved)")
    except Exception as reload_exc:  # noqa: BLE001
        try:
            device = DeviceApp(spec.make_state(), spec.view, make_bridge())
            current["device"] = device
            await device.start()
            log(f"[tempest] hot-restarted (state reset: {reload_exc})")
        except Exception:  # noqa: BLE001 - the clean restart also failed
            await _mount_error(current, make_bridge, log, traceback.format_exc())


async def _mount_error(
    current: dict[str, Any],
    make_bridge: Callable[[], Bridge],
    log: Callable[[str], None],
    detail: str,
) -> None:
    """Mount a red error screen on the device and flag the error state.

    Args:
        current: The mutable load state (``device``/``error``).
        make_bridge: Factory for a fresh :class:`Bridge`.
        log: Sink for status lines.
        detail: The traceback / error detail to show on-device.
    """
    log(f"[tempest] app failed to load:\n{detail}")
    device: DeviceApp[Any] = DeviceApp(
        None, lambda _app: error_screen("App failed to load", detail), make_bridge()
    )
    current["device"] = device
    current["error"] = True
    await device.start()


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

    async def _fetch(target: str) -> bytes:
        """Fetch a URL body (raw bytes) off the event loop thread."""

        def _get() -> bytes:
            # A generous timeout: the first poll races the cold-start of the
            # ``adb reverse`` tunnel, and ``/bundle`` can be a large multi-file
            # archive — 10s was tight enough to spuriously time out on both.
            with urllib.request.urlopen(target, timeout=30) as response:  # noqa: S310
                return response.read()

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
