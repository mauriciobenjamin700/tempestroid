import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from tempest_core.core.ir import Node

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


async def test_mount_carries_theme_mode_default_system():
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    # The host maps theme_mode → Material colorScheme; default defers to the OS.
    assert bridge.sent[0]["theme_mode"] == "system"


async def test_dark_theme_propagates_to_mount():
    from tempest_core import Theme, ThemeMode

    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    device.app.set_theme(Theme(mode=ThemeMode.DARK))
    await device.start()
    # A dark app forces the host's dark Material scheme, so Material primitives
    # (TextField, dropdown, slider) match instead of falling to the OS-light scheme.
    assert bridge.sent[0]["theme_mode"] == "dark"


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


# --- overlays over the bridge ----------------------------------------------


def _overlay_view(app: "App[Counter]") -> Widget:
    return Text(content="root", key="root")


async def test_mount_serializes_overlays_with_barrier_and_key():
    from tempestroid import Dialog

    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _overlay_view, bridge)
    await device.start()
    overlay_id = device.app.show_dialog(Dialog(title="Hi"))
    await _drain()

    # A fresh mount carries no overlays; the dialog rides the next patch batch,
    # but a subsequent start would serialize it under `overlays`.
    bridge2 = LoopbackBridge()

    def _view_with_overlay(app: "App[Counter]") -> Widget:
        return Text(content="root", key="root")

    device2: DeviceApp[Counter] = DeviceApp(Counter(), _view_with_overlay, bridge2)
    await device2.start()
    device2.app.show_dialog(Dialog(title="Hi"))
    await _drain()
    # The patch batch carried a namespaced overlay insert.
    patch_msgs = [m for m in bridge2.sent if m["kind"] == "patch"]
    overlay_inserts = [
        p
        for m in patch_msgs
        for p in m["patches"]
        if p["op"] == "insert" and p["path"] == ["overlay"]
    ]
    assert overlay_inserts
    assert overlay_inserts[0]["node"]["type"] == "Dialog"
    assert overlay_inserts[0]["node"]["props"]["barrier"] is True
    assert overlay_id  # the first device returned a stable id


async def test_patch_path_is_json_safe_for_overlay():
    import json

    from tempestroid import Dialog

    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _overlay_view, bridge)
    await device.start()
    device.app.show_dialog(Dialog(title="Hi"))
    await _drain()
    # The whole patch batch round-trips through JSON (paths are list[int|str]).
    patch_msgs = [m for m in bridge.sent if m["kind"] == "patch"]
    assert patch_msgs
    json.dumps(patch_msgs[-1])  # must not raise
    inserts = [p for p in patch_msgs[-1]["patches"] if p["op"] == "insert"]
    assert inserts[0]["path"] == ["overlay"]


async def test_dismiss_token_routes_to_app_dismiss():
    from tempestroid import Dialog

    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _overlay_view, bridge)
    await device.start()
    overlay_id = device.app.show_dialog(Dialog(title="Hi"))
    await _drain()
    assert device.app.current_tree is not None
    assert len(device.app.current_tree.overlays) == 1

    # A host-owned dismiss arrives over the event channel as __dismiss__:<id>.
    await device.handle_event(
        {"kind": "event", "token": f"__dismiss__:{overlay_id}", "payload": {}}
    )
    await _drain()
    assert device.app.current_tree is not None
    assert device.app.current_tree.overlays == []


async def test_overlay_handler_token_resolves_after_refresh():
    from tempestroid import Dialog

    bridge = LoopbackBridge()
    dismissed: list[int] = []

    def view(app: "App[Counter]") -> Widget:
        return Text(content="root", key="root")

    device: DeviceApp[Counter] = DeviceApp(Counter(), view, bridge)
    await device.start()
    device.app.show_dialog(Dialog(title="Hi", on_dismiss=lambda: dismissed.append(1)))
    await _drain()
    # The overlay's on_dismiss handler is registered under the namespaced token.
    await device.handle_event(
        {"kind": "event", "token": "overlay/0:on_dismiss", "payload": {}}
    )
    await _drain()
    assert dismissed == [1]


def test_event_schemas_register_overlay_widgets():
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    for widget_type in ("Dialog", "BottomSheet", "Menu", "Popover", "ActionSheet"):
        assert widget_type in EVENT_SCHEMAS
    assert EVENT_SCHEMAS["Dialog"]["on_dismiss"].__name__ == "DismissEvent"
    assert EVENT_SCHEMAS["Menu"]["on_select"].__name__ == "MenuSelectEvent"


# --- E3: the animation frame flag crossing the wire --------------------------
#
# ``has_animations`` rides every mount/patch so the Compose host can start/stop
# its ``withFrameNanos`` loop without a synchronous round-trip. These pin that it
# is serialized and tracks the live set of active controllers.


async def test_mount_reports_has_animations_false_without_animation():
    """A mount with no active controller carries ``has_animations == False``."""
    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    assert bridge.sent[0]["has_animations"] is False


async def test_patch_reports_has_animations_true_while_active():
    """A controller registered on the app flips ``has_animations`` on the patch.

    Registering a controller starts the app's frame clock (``_animations``
    non-empty), so the next coalesced patch batch must report
    ``has_animations == True`` — the signal the Kotlin host reads to spin up its
    ``withFrameNanos`` loop and start emitting the reserved frame token.
    """
    from tempest_core.animation import AnimationController

    bridge = LoopbackBridge()
    device: DeviceApp[Counter] = DeviceApp(Counter(), _counter_view, bridge)
    await device.start()
    assert bridge.sent[0]["has_animations"] is False

    ctrl = AnimationController(duration_s=1.0)
    device.app.register_animation(ctrl)
    ctrl.forward()
    assert device.app.has_animations is True

    # Force a rebuild so a patch batch is emitted while the controller is active.
    device.app.set_state(lambda s: setattr(s, "value", s.value + 1))
    await _drain()

    patch_msgs = [m for m in bridge.sent if m["kind"] == "patch"]
    assert patch_msgs, "expected at least one patch batch"
    assert patch_msgs[-1]["has_animations"] is True


def test_mount_message_default_has_animations_false():
    """The wire model defaults ``has_animations`` to ``False`` (no animation)."""
    from tempestroid.bridge.protocol import MountMessage, PatchMessage

    assert MountMessage(root={}).has_animations is False
    assert PatchMessage(patches=[]).has_animations is False
    dumped = MountMessage(root={}, has_animations=True).model_dump()
    assert dumped["has_animations"] is True
