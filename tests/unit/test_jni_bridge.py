"""Tests for the device JNI transport (phase B3, Python half).

The native ``_tempest_host`` module exists only inside the Android app, so these
tests stub it in ``sys.modules`` to exercise :class:`JniBridge` and the event
sink wiring without a device.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid.bridge.device import DeviceApp, LoopbackBridge
from tempestroid.bridge.jni import JniBridge, make_event_sink, run_device
from tempestroid.bridge.protocol import BACK_TOKEN, FRAME_TOKEN
from tempestroid.core.state import App
from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX
from tempestroid.navigation import Route
from tempestroid.widgets import Text, Widget


def _fake_host() -> types.ModuleType:
    """Build a stand-in ``_tempest_host`` module recording its calls.

    Returns:
        A module exposing ``send_to_host`` / ``set_event_sink`` plus the captured
        ``sent`` list and ``sink`` reference.
    """
    module = types.ModuleType("_tempest_host")
    sent: list[str] = []
    module.sent = sent  # type: ignore[attr-defined]
    module.sink = None  # type: ignore[attr-defined]
    module.send_to_host = lambda message: sent.append(message)  # type: ignore[attr-defined]

    def _set_sink(cb: Any) -> None:
        module.sink = cb  # type: ignore[attr-defined]

    module.set_event_sink = _set_sink  # type: ignore[attr-defined]
    return module


def test_jni_bridge_raises_off_device() -> None:
    """Constructing a ``JniBridge`` fails clearly when the native module is absent."""
    sys.modules.pop("_tempest_host", None)
    with pytest.raises(RuntimeError, match="_tempest_host is unavailable"):
        JniBridge()


async def test_jni_bridge_sends_json() -> None:
    """``JniBridge.send`` JSON-encodes and forwards to ``send_to_host``."""
    host = _fake_host()
    sys.modules["_tempest_host"] = host
    try:
        bridge = JniBridge()
        await bridge.send({"kind": "mount", "root": {"type": "Text"}})
    finally:
        del sys.modules["_tempest_host"]

    assert len(host.sent) == 1  # type: ignore[attr-defined]
    decoded = json.loads(host.sent[0])  # type: ignore[attr-defined]
    assert decoded == {"kind": "mount", "root": {"type": "Text"}}


# --- E0d: event-sink routing of the reserved channels ------------------------
#
# The event sink (the host → Python entry point) multiplexes three channels over
# the single JNI event transport: the reserved BACK_TOKEN, the NATIVE_RESULT_PREFIX
# tokens, and ordinary widget-handler tokens. These tests pin each branch so a
# regression that reorders/collapses them (e.g. routing __back__ through the
# widget registry, or treating a payload-bearing back as a widget event) is caught.


@dataclass
class _NavState:
    """Minimal state for the device-app event-sink tests."""

    value: int = 0


def _route_view(app: App[_NavState]) -> Widget:
    """Build a screen labelled by the active route name."""
    return Text(content=app.nav.top.name)


def _device_with_stack(*names: str) -> tuple[DeviceApp[_NavState], LoopbackBridge]:
    """Build a started device app whose nav stack holds the given route names.

    Args:
        names: The route names, root first.

    Returns:
        The device app and its loopback bridge (already mounted).
    """
    bridge = LoopbackBridge()
    device: DeviceApp[_NavState] = DeviceApp(_NavState(), _route_view, bridge)
    device.app.nav.stack = [Route(name=name) for name in names]
    return device, bridge


async def test_back_token_routes_to_pop_not_to_handle_event() -> None:
    """``__back__`` reaches ``App.pop`` and is never dispatched as a widget event.

    Guards the contract that the back channel short-circuits *before* the widget
    handler path: ``handle_event`` (the registry dispatch) must never see the
    reserved token.
    """
    device, _ = _device_with_stack("/", "/a")
    seen: list[dict[str, Any]] = []
    original = device.handle_event

    async def _spy(message: dict[str, Any]) -> None:
        seen.append(message)
        await original(message)

    device.handle_event = _spy  # type: ignore[method-assign]
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(BACK_TOKEN, "")
    for _ in range(4):
        await asyncio.sleep(0)

    assert [r.name for r in device.app.nav.stack] == ["/"]
    # the reserved token must not have been dispatched as a widget handler event
    assert seen == []


async def test_back_token_with_nonempty_payload_still_pops() -> None:
    """A ``__back__`` event still pops even if the host attaches a payload.

    The host sends ``dispatchEvent("__back__", "{}")``; the routing keys off the
    token alone, so a non-empty (but valid-JSON) payload must not divert it.
    """
    device, _ = _device_with_stack("/", "/a", "/b")
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(BACK_TOKEN, '{"ignored": true}')
    for _ in range(4):
        await asyncio.sleep(0)

    assert [r.name for r in device.app.nav.stack] == ["/", "/a"]


async def test_native_result_branch_is_independent_of_back() -> None:
    """A native-result token resolves its future and does not touch the nav stack.

    Pins that ``__back__`` and ``__native_result__:`` are *distinct* branches:
    the native channel keeps working unchanged alongside the new back channel.
    """
    device, _ = _device_with_stack("/", "/a")
    await device.start()

    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    from tempestroid.native import dispatch as _dispatch

    _dispatch._pending["42"] = future  # type: ignore[attr-defined]
    try:
        sink = make_event_sink(loop, device)
        sink(f"{NATIVE_RESULT_PREFIX}42", '{"ok": true}')
        for _ in range(4):
            await asyncio.sleep(0)

        assert future.done()
        assert future.result() == {"ok": True}
        # the native result must not have disturbed navigation
        assert [r.name for r in device.app.nav.stack] == ["/", "/a"]
    finally:
        _dispatch._pending.pop("42", None)  # type: ignore[attr-defined]


async def test_frame_token_routes_to_tick_not_to_handle_event() -> None:
    """``__frame__`` reaches ``App._tick_from_device`` and is never a widget event.

    The device host emits the reserved frame token once per ``withFrameNanos``
    frame while an animation is active; the sink must route it straight to the
    app's device-driven clock tick, short-circuiting before the widget handler
    path (``handle_event`` must never see it).
    """
    device, _ = _device_with_stack("/")
    ticks: list[int] = []
    seen: list[dict[str, Any]] = []
    original_handle = device.handle_event
    original_tick = device.app._tick_from_device  # type: ignore[attr-defined]

    async def _spy_handle(message: dict[str, Any]) -> None:
        seen.append(message)
        await original_handle(message)

    def _spy_tick() -> None:
        ticks.append(1)
        original_tick()

    device.handle_event = _spy_handle  # type: ignore[method-assign]
    device.app._tick_from_device = _spy_tick  # type: ignore[method-assign]
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(FRAME_TOKEN, "")
    for _ in range(4):
        await asyncio.sleep(0)

    assert ticks == [1]
    # the frame token must not have been dispatched as a widget handler event
    assert seen == []


async def test_frame_token_with_payload_still_ticks() -> None:
    """A ``__frame__`` event still ticks even if the host attaches a payload.

    Routing keys off the token alone (and short-circuits before the JSON parse),
    so a non-empty payload must not divert it to the widget path.
    """
    device, _ = _device_with_stack("/")
    ticks: list[int] = []
    original_tick = device.app._tick_from_device  # type: ignore[attr-defined]

    def _spy_tick() -> None:
        ticks.append(1)
        original_tick()

    device.app._tick_from_device = _spy_tick  # type: ignore[method-assign]
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(FRAME_TOKEN, '{"ignored": true}')
    for _ in range(4):
        await asyncio.sleep(0)

    assert ticks == [1]


def test_frame_token_constant_is_payload_free_sentinel() -> None:
    """``FRAME_TOKEN`` carries no ``:`` separator and is distinct from BACK_TOKEN."""
    assert ":" not in FRAME_TOKEN
    assert FRAME_TOKEN != BACK_TOKEN
    assert not FRAME_TOKEN.startswith(NATIVE_RESULT_PREFIX)


def test_back_token_constant_has_no_payload_separator() -> None:
    """``BACK_TOKEN`` carries no ``:`` separator (payload-free, unlike handler tokens).

    Handler tokens are ``"<path>:<prop>"`` and native results ``"<prefix>:<id>"``;
    the back token is a bare sentinel so it can never collide with either.
    """
    assert ":" not in BACK_TOKEN
    assert not BACK_TOKEN.startswith(NATIVE_RESULT_PREFIX)


# --- E0d: deep link wired through the run_device entry point -----------------


def test_run_device_resolves_route_into_initial_stack() -> None:
    """``run_device(route=...)`` opens on the deep-linked stack via ``reset``.

    Exercises the actual device entry point (with a stubbed native host and a
    loop that exits immediately) to prove the ``tempest_route`` intent extra is
    resolved into the initial :class:`NavStack` before the first mount — the
    Python half of the Android deep-link path.
    """
    host = _fake_host()
    sys.modules["_tempest_host"] = host
    captured: list[list[Route]] = []

    def _view(app: App[_NavState]) -> Widget:
        # record the stack the app booted with (read at first build)
        captured.append(list(app.nav.stack))
        return Text(content=app.nav.top.name)

    real_new_loop = asyncio.new_event_loop

    def _fake_new_loop() -> asyncio.AbstractEventLoop:
        # build a real loop, but replace its blocking run_forever with a single
        # drain so run_device returns after the scheduled start() completes.
        # run_until_complete delegates to run_forever, so keep the original bound
        # method to avoid recursing into the override.
        loop = real_new_loop()
        original_run_forever = loop.run_forever

        def _drain() -> None:
            loop.call_later(0.01, loop.stop)
            original_run_forever()

        loop.run_forever = _drain  # type: ignore[method-assign]
        return loop

    asyncio.new_event_loop = _fake_new_loop  # type: ignore[assignment]
    try:
        run_device(_NavState(), _view, route="/shop/item")
    finally:
        asyncio.new_event_loop = real_new_loop  # type: ignore[assignment]
        del sys.modules["_tempest_host"]
        asyncio.set_event_loop(None)

    assert captured, "view was never built"
    assert [r.name for r in captured[0]] == ["/", "/shop", "/shop/item"]
    # the mount the host received reflects the deep-linked (poppable) stack
    mount = json.loads(host.sent[-1])  # type: ignore[attr-defined]
    assert mount["kind"] == "mount"
    assert mount["can_pop"] is True


# === phase E8: reserved stream tokens route to the native dispatch hooks =====
#
# Sensor samples, lifecycle transitions and connectivity changes ride the same
# single event transport under reserved tokens (like FRAME_TOKEN / BACK_TOKEN /
# the native result prefix). The sink must route them to the matching native
# callback registry, NEVER to a widget handler.


async def test_sensor_token_routes_to_sensor_registry(monkeypatch: Any) -> None:
    """``__sensor__:<type>`` reaches the sensor dispatch hook, not handle_event."""
    from tempestroid.bridge import jni as jni_mod
    from tempestroid.bridge.protocol import SENSOR_TOKEN_PREFIX

    device, _ = _device_with_stack("/")
    seen: list[dict[str, Any]] = []
    samples: list[tuple[str, dict[str, Any]]] = []
    original_handle = device.handle_event

    async def _spy_handle(message: dict[str, Any]) -> None:
        seen.append(message)
        await original_handle(message)

    def _spy_sensor(sensor_type: str, payload: dict[str, Any]) -> None:
        samples.append((sensor_type, payload))

    device.handle_event = _spy_handle  # type: ignore[method-assign]
    monkeypatch.setattr(jni_mod, "dispatch_sensor_event", _spy_sensor)
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(f"{SENSOR_TOKEN_PREFIX}:accelerometer", '{"values": [1.0, 2.0]}')
    for _ in range(4):
        await asyncio.sleep(0)

    assert samples == [("accelerometer", {"values": [1.0, 2.0]})]
    assert seen == []


async def test_lifecycle_token_routes_to_lifecycle_registry() -> None:
    """``__lifecycle__`` reaches the lifecycle callback, not handle_event."""
    from tempestroid.bridge.protocol import LIFECYCLE_TOKEN
    from tempestroid.native.lifecycle import on_app_state_change
    from tempestroid.widgets.events import AppState, LifecycleEvent

    device, _ = _device_with_stack("/")
    states: list[AppState] = []

    def _record(event: LifecycleEvent) -> None:
        states.append(event.state)

    unregister = on_app_state_change(_record)
    await device.start()
    try:
        loop = asyncio.get_running_loop()
        sink = make_event_sink(loop, device)
        sink(LIFECYCLE_TOKEN, '{"state": "background"}')
        for _ in range(4):
            await asyncio.sleep(0)
    finally:
        unregister()

    assert states == [AppState.BACKGROUND]
    assert isinstance(LifecycleEvent(state=AppState.BACKGROUND), LifecycleEvent)


async def test_connectivity_token_routes_to_connectivity_registry(
    monkeypatch: Any,
) -> None:
    """``__connectivity__:<state>`` reaches the connectivity dispatch hook."""
    from tempestroid.bridge import jni as jni_mod
    from tempestroid.bridge.protocol import CONNECTIVITY_TOKEN_PREFIX

    device, _ = _device_with_stack("/")
    seen: list[dict[str, Any]] = []

    def _spy_connectivity(payload: dict[str, Any]) -> None:
        seen.append(payload)

    monkeypatch.setattr(jni_mod, "dispatch_connectivity_event", _spy_connectivity)
    await device.start()

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(f"{CONNECTIVITY_TOKEN_PREFIX}:wifi", '{"state": "wifi"}')
    for _ in range(4):
        await asyncio.sleep(0)

    assert seen == [{"state": "wifi"}]
