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
import logging
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from tempestroid.bridge.device import Bridge, DeviceApp
from tempestroid.bridge.protocol import (
    BACK_TOKEN,
    BACKGROUND_TOKEN_PREFIX,
    CONNECTIVITY_TOKEN_PREFIX,
    DISMISS_TOKEN_PREFIX,
    FRAME_TOKEN,
    LIFECYCLE_TOKEN,
    LOCALE_TOKEN,
    SENSOR_TOKEN_PREFIX,
    THEME_TOKEN,
)
from tempestroid.core.state import App
from tempestroid.i18n import Locale
from tempestroid.native.background import dispatch_background_task
from tempestroid.native.connectivity import dispatch_connectivity_event
from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX, resolve_native_result
from tempestroid.native.lifecycle import dispatch_lifecycle_event
from tempestroid.native.sensors import dispatch_sensor_event
from tempestroid.navigation import NavStack, routes_from_path
from tempestroid.widgets import Widget
from tempestroid.widgets.events import (
    LocaleChangeEvent,
    ThemeChangeEvent,
    parse_event,
)

__all__ = [
    "JniBridge",
    "make_event_sink",
    "run_device",
    "run_device_file",
    "run_device_bundle",
    "run_device_error",
]

_LOGGER: logging.Logger = logging.getLogger(__name__)

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


def make_event_sink(
    loop: asyncio.AbstractEventLoop, device: DeviceApp[S]
) -> Callable[[str, str], None]:
    """Build the native event sink that marshals device events onto the loop.

    The returned callable is what the host invokes (from the UI thread, with the
    GIL held) for every incoming device event. It only schedules work onto the
    loop via ``call_soon_threadsafe`` and returns fast, and it routes the
    reserved channels that share the event transport:

    * :data:`~tempestroid.bridge.protocol.FRAME_TOKEN` — one animation frame from
      the host's ``withFrameNanos`` loop → ``App._tick_from_device`` (advances the
      animation clock one frame). Routed first since it is the highest-frequency,
      payload-free channel.
    * :data:`~tempestroid.bridge.protocol.BACK_TOKEN` — a system back action →
      :meth:`~tempestroid.App.pop` (pops a screen, or a no-op at the root).
    * :data:`~tempestroid.native.dispatch.NATIVE_RESULT_PREFIX` — a native
      request/response result → :func:`resolve_native_result`.
    * any other token — a widget handler event → :meth:`DeviceApp.handle_event`.

    Args:
        loop: The asyncio loop the device app runs on.
        device: The device app to route events into.

    Returns:
        The ``(token, payload_json) -> None`` sink to register with the host.
    """

    def _on_event(token: str, payload_json: str) -> None:
        """Native callback: schedule an incoming event onto the loop.

        Args:
            token: The handler token addressed by the event.
            payload_json: The raw JSON payload (``""`` for none).
        """
        # An animation frame tick rides the same event channel under the reserved
        # FRAME_TOKEN, sent once per frame by the host's ``withFrameNanos`` loop
        # while an animation is active. It is payload-free and the hottest channel,
        # so it short-circuits before the JSON parse straight to the app's
        # device-driven clock tick (which advances every active controller one
        # frame and re-renders). Like BACK_TOKEN it needs no extra JNI entry point.
        if token == FRAME_TOKEN:
            loop.call_soon_threadsafe(device.app._tick_from_device)  # pyright: ignore[reportPrivateUsage]
            return
        # A native callback must never raise back into JNI: a malformed payload
        # is dropped (logged) instead of crashing the host on the UI thread.
        try:
            payload: dict[str, Any] = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            _LOGGER.exception(
                "dropping event for token %r: invalid JSON payload", token
            )
            return
        # A system back action (e.g. the Android back gesture) rides the same
        # event channel under the reserved BACK_TOKEN, so it needs no extra JNI
        # entry point. Route it straight to App.pop, which pops a screen (and
        # rebuilds) or is a no-op at the root. The host only sends this when its
        # back handler is enabled (can_pop True), so a root no-op is benign.
        if token == BACK_TOKEN:
            loop.call_soon_threadsafe(device.app.pop)
            return
        # An overlay dismissed by a host-owned gesture (scrim tap, swipe-down)
        # rides the same event channel under the reserved __dismiss__:<id>
        # token, so it needs no extra JNI entry point. Route the id straight to
        # App.dismiss (a no-op if the overlay already closed).
        dismiss_prefix = f"{DISMISS_TOKEN_PREFIX}:"
        if token.startswith(dismiss_prefix):
            overlay_id = token[len(dismiss_prefix) :]
            loop.call_soon_threadsafe(device.app.dismiss, overlay_id)
            return
        # Native request/response results ride the same event channel under a
        # reserved token, so they need no extra JNI entry point. Route them to
        # the pending-future resolver instead of the widget handler registry.
        if token.startswith(NATIVE_RESULT_PREFIX):
            request_id = token[len(NATIVE_RESULT_PREFIX) :]
            loop.call_soon_threadsafe(resolve_native_result, request_id, payload)
            return
        # Continuous sensor samples ride the same event channel under the
        # reserved "__sensor__:<type>" token (one event per sample while the
        # stream is open) — route them to the sensor callback registry. Like the
        # native result they need no new JNI entry point.
        sensor_prefix = f"{SENSOR_TOKEN_PREFIX}:"
        if token.startswith(sensor_prefix):
            sensor_type = token[len(sensor_prefix) :]
            loop.call_soon_threadsafe(dispatch_sensor_event, sensor_type, payload)
            return
        # An app-lifecycle transition (foreground/background) rides the same
        # event channel under the reserved LIFECYCLE_TOKEN — route it to the
        # lifecycle callback registry.
        if token == LIFECYCLE_TOKEN:
            loop.call_soon_threadsafe(dispatch_lifecycle_event, payload)
            return
        # A network-connectivity change rides the same event channel under the
        # reserved "__connectivity__:<state>" token — route it to the
        # connectivity callback registry.
        if token.startswith(f"{CONNECTIVITY_TOKEN_PREFIX}:"):
            loop.call_soon_threadsafe(dispatch_connectivity_event, payload)
            return
        # A fired background task (WorkManager) rides the same event channel under
        # the reserved "__background__:<name>" token — route the name to the
        # background handler registry (this is the live-interpreter path; a
        # dead-process wake boots a fresh interpreter and calls
        # run_device_background directly instead).
        background_prefix = f"{BACKGROUND_TOKEN_PREFIX}:"
        if token.startswith(background_prefix):
            task_name = token[len(background_prefix) :]
            loop.call_soon_threadsafe(dispatch_background_task, task_name)
            return
        # A theme-mode change (OS dark-mode toggle, or app-requested switch) rides
        # the same event channel under the reserved THEME_TOKEN. Validate the
        # payload at the boundary, then swap the app's theme (which rebuilds).
        if token == THEME_TOKEN:
            event = parse_event(ThemeChangeEvent, payload)
            loop.call_soon_threadsafe(
                lambda: device.app.set_theme(
                    device.app.theme.model_copy(update={"mode": event.mode})
                )
            )
            return
        # A locale / layout-direction change rides the same event channel under
        # the reserved LOCALE_TOKEN. Validate and swap the app's locale.
        if token == LOCALE_TOKEN:
            locale_event = parse_event(LocaleChangeEvent, payload)
            loop.call_soon_threadsafe(
                lambda: device.app.set_locale(
                    Locale(
                        language=locale_event.language,
                        region=locale_event.region,
                        rtl=locale_event.rtl,
                    )
                )
            )
            return
        message: dict[str, Any] = {
            "kind": "event",
            "token": token,
            "payload": payload,
        }
        loop.call_soon_threadsafe(
            lambda: loop.create_task(device.handle_event(message))
        )

    return _on_event


def run_device(
    state: S, view: Callable[[App[S]], Widget], route: str | None = None
) -> None:
    """Boot a :class:`DeviceApp` on a fresh asyncio loop and run it forever.

    This is the device-side analogue of ``run_qt``: it owns the loop, sends the
    initial ``mount`` over a :class:`JniBridge`, registers the native event sink
    (which marshals incoming device events back onto the loop), and blocks in
    ``run_forever``. Call it from the interpreter's main thread inside the host —
    the Kotlin side already runs the interpreter off the UI thread.

    Args:
        state: The initial application state.
        view: Builds the widget tree from the app.
        route: Optional deep-link path (e.g. the Android ``tempest_route`` intent
            extra). When given it is resolved via :func:`routes_from_path` into
            the initial navigation stack, so the app opens directly on the linked
            screen with its back stack already built.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    nav = NavStack(stack=routes_from_path(route)) if route else None
    device: DeviceApp[S] = DeviceApp(state, view, JniBridge(), nav=nav)

    native_host().set_event_sink(make_event_sink(loop, device))
    loop.create_task(device.start())
    loop.run_forever()


def run_device_error(title: str, detail: str) -> None:
    """Boot a minimal app showing an error screen, then run forever.

    The fallback for the baked-APK entry points when loading the user's app
    fails: rather than leave the device on a blank white screen with the cause
    buried in ``logcat``, mount a visible red error screen carrying the
    traceback. The interpreter stays live so the screen persists.

    Args:
        title: A short, human summary (e.g. ``"App failed to load"``).
        detail: The error detail / traceback to show on the device.
    """
    from tempestroid.bridge.errors import error_screen

    run_device(None, lambda _app: error_screen(title, detail))


def run_device_file(path: str, route: str | None = None) -> None:
    """Load an app file (``make_state`` + ``view``) and run it on the device.

    The device entry point for an APK bundled by ``tempest build``: the user's
    app source is packaged as an asset, extracted to ``path`` on first launch,
    and run here. Mirrors :func:`run_device` but sources the state/view from a
    file via the same loader the dev cockpit and code-push client use. A load
    failure (e.g. the app file imports the Qt renderer at module level, which is
    absent on the device) surfaces as an on-device error screen instead of a
    blank white window.

    Args:
        path: Absolute path to the extracted app file on the device.
        route: Optional deep-link path forwarded to :func:`run_device` (the
            Android ``tempest_route`` intent extra) to open on the linked screen.
    """
    import traceback
    from pathlib import Path

    from tempestroid.cli.app_loader import spec_from_source

    try:
        source = Path(path).read_text(encoding="utf-8")
        spec = spec_from_source(source, filename=path)
        state, view = spec.make_state(), spec.view
    except Exception:  # noqa: BLE001 - surface any load failure on-device
        run_device_error("App failed to load", traceback.format_exc())
        return
    run_device(state, view, route=route)


def run_device_bundle(zip_path: str, route: str | None = None) -> None:
    """Extract a project bundle and run its app standalone on the device.

    The device entry point for a multi-file APK built by ``tempest build``: the
    user's whole project tree is packaged as a ``tempest_app_bundle.zip`` asset,
    copied to ``zip_path`` on first launch, and run here. The bundle is extracted
    next to the zip, its root placed on ``sys.path`` (so ``from my_pkg import x``
    resolves), and the manifest's entry module loaded — then the app runs exactly
    like :func:`run_device_file`, but for a project rather than a single file.

    Args:
        zip_path: Absolute path to the extracted bundle ``.zip`` on the device.
        route: Optional deep-link path forwarded to :func:`run_device` (the
            Android ``tempest_route`` intent extra) to open on the linked screen.
    """
    import traceback
    from pathlib import Path

    from tempestroid.cli.app_loader import spec_from_project
    from tempestroid.cli.bundle import extract_bundle

    try:
        archive = Path(zip_path)
        data = archive.read_bytes()
        layout = extract_bundle(data, archive.parent / "tempest_app")
        spec = spec_from_project(layout.root, layout.entry)
        state, view = spec.make_state(), spec.view
    except Exception:  # noqa: BLE001 - surface any load failure on-device
        run_device_error("App failed to load", traceback.format_exc())
        return
    run_device(state, view, route=route)
