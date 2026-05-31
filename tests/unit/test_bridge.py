import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid import (
    App,
    Button,
    Column,
    DeviceApp,
    EventValidationError,
    LoopbackBridge,
    Text,
    Widget,
)
from tempestroid.bridge import HandlerRegistry
from tempestroid.core.ir import Node


@dataclass
class Counter:
    value: int = 0


def _counter_view(app: "App[Counter]") -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ]
    )


def _labels(message: dict[str, Any]) -> list[str]:
    out: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        if node["type"] == "Text":
            out.append(node["props"]["content"])
        for child in node["children"]:
            walk(child)

    walk(message["root"])
    return out


async def _drain() -> None:
    """Let coalesced rebuilds and their async send tasks finish."""
    for _ in range(20):
        await asyncio.sleep(0)


async def test_start_sends_mount_message():
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    assert len(bridge.sent) == 1
    assert bridge.sent[0]["kind"] == "mount"
    assert _labels(bridge.sent[0]) == ["Count: 0"]


async def test_tap_event_round_trip_updates_and_patches():
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()

    # The button's handler token lives at child index 1.
    await device.handle_event({"kind": "event", "token": "1:on_click", "payload": {}})
    await _drain()  # let the coalesced rebuild + async send run

    assert device.app.state.value == 1
    assert len(bridge.sent) == 2
    patch_msg = bridge.sent[1]
    assert patch_msg["kind"] == "patch"
    update = patch_msg["patches"][0]
    assert update["op"] == "update"
    assert update["set"] == {"content": "Count: 1"}


async def test_unknown_token_is_noop():
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    await device.handle_event({"kind": "event", "token": "9:on_click", "payload": {}})
    await _drain()
    assert device.app.state.value == 0
    assert len(bridge.sent) == 1  # no patch emitted


def test_registry_registers_handler_token():
    registry = HandlerRegistry()
    # A node whose handler expects a TapEvent (Button.on_click).
    root = Node(type="Button", key="b", props={"label": "x", "on_click": lambda: None})
    registry.refresh(root)
    assert "root:on_click" in registry.tokens()


async def test_registry_dispatch_invokes_handler():
    registry = HandlerRegistry()
    calls: list[int] = []
    root = Node(type="Button", props={"on_click": lambda: calls.append(1)})
    registry.refresh(root)
    assert await registry.dispatch("root:on_click", {})
    assert calls == [1]


async def test_registry_dispatch_rejects_bad_payload():
    registry = HandlerRegistry()
    # TapEvent has only optional fields, so feed a wrong-typed value to fail.
    root = Node(type="Button", props={"on_click": lambda: None})
    registry.refresh(root)
    with pytest.raises(EventValidationError):
        await registry.dispatch("root:on_click", {"x": "not-a-number"})


def _counter_view_b(app: "App[Counter]") -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(content=f"NEW: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ]
    )


async def test_device_reload_preserves_state_and_patches():
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    await device.handle_event({"kind": "event", "token": "1:on_click", "payload": {}})
    await _drain()
    assert device.app.state.value == 1

    device.reload(_counter_view_b)
    await _drain()
    # State survives the reload; a patch reflecting the new view is sent.
    assert device.app.state.value == 1
    assert bridge.sent[-1]["kind"] == "patch"

    # Handlers from the reloaded view still work.
    await device.handle_event({"kind": "event", "token": "1:on_click", "payload": {}})
    await _drain()
    assert device.app.state.value == 2
