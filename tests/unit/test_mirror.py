"""Unit tests for the F9 host-side scene mirror.

These prove the mirror (``deserialize_scene`` + ``apply_patches``) reconstructs
exactly what the engine's own serializer emits: a counter app is driven through
real ``DeviceApp`` mount + tap → patch cycles over a :class:`LoopbackBridge`, and
the mirror's reconstructed tree is compared field-by-field against the engine's
freshly-rebuilt serialized tree. No emulator, no adb — pure determinism.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.bridge.device import DeviceApp, LoopbackBridge
from tempestroid.bridge.serializer import serialize_node
from tempestroid.testing.mirror import apply_patches, deserialize_scene


@dataclass
class CounterState:
    """Mutable counter state.

    Attributes:
        value: The current count.
    """

    value: int = 0


def make_state() -> CounterState:
    """Build a fresh counter state.

    Returns:
        A new state at zero.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Build a minimal counter UI (label + increment button).

    Args:
        app: The running app.

    Returns:
        The root widget.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ]
    )


def _strip_event_annotations(node: dict[str, Any]) -> dict[str, Any]:
    """Drop the cosmetic ``event`` key from every handler ref in a serialized tree.

    A full ``serialize_node`` (mount) annotates each handler ref with its
    ``event`` name, but an ``Update`` patch's ``set_props`` is serialized with an
    unknown node type and so omits it. That annotation never crosses to the device
    on a patch either, so the mirror faithfully lacks it after an update. Stripping
    it on both sides compares the load-bearing structure (the ``$handler`` token).

    Args:
        node: A serialized node dict.

    Returns:
        The node with ``event`` removed from every handler ref, recursively.
    """
    props: dict[str, Any] = {}
    raw_props: dict[str, Any] = node.get("props", {})
    for name, value in raw_props.items():
        if isinstance(value, dict) and "$handler" in value:
            props[name] = {"$handler": value["$handler"]}
        else:
            props[name] = value
    children: list[dict[str, Any]] = node.get("children", [])
    return {
        "type": node["type"],
        "key": node["key"],
        "props": props,
        "children": [_strip_event_annotations(child) for child in children],
    }


def _expected_serialized_root(device: DeviceApp[CounterState]) -> dict[str, Any]:
    """Serialize the device app's current root the way the engine does on mount.

    Args:
        device: The running device app.

    Returns:
        The serialized root node dict (the ground truth the mirror must match),
        with cosmetic ``event`` annotations stripped (see
        :func:`_strip_event_annotations`).
    """
    tree = device.app.current_tree
    assert tree is not None
    return _strip_event_annotations(serialize_node(tree.root))


@pytest.mark.asyncio
async def test_mount_round_trips_to_mirror() -> None:
    """The mirror reconstructed from the mount JSON equals the engine's tree."""
    bridge = LoopbackBridge()
    device: DeviceApp[CounterState] = DeviceApp(make_state(), view, bridge)
    await device.start()

    mount = bridge.sent[0]
    assert mount["kind"] == "mount"
    scene = deserialize_scene(mount)

    # The mirror root equals what the engine would serialize right now (the mount
    # keeps event annotations; both sides stripped to compare the structure).
    assert _strip_event_annotations(serialize_node(scene.root)) == (
        _expected_serialized_root(device)
    )
    # The mirror keeps the handler token (the callable never crosses).
    button = scene.root.children[1]
    assert button.props["on_click"]["$handler"] == "1:on_click"


@pytest.mark.asyncio
async def test_patches_track_engine_rebuild_across_taps() -> None:
    """Applying serialized patch batches keeps the mirror equal to the engine."""
    bridge = LoopbackBridge()
    device: DeviceApp[CounterState] = DeviceApp(make_state(), view, bridge)
    await device.start()
    scene = deserialize_scene(bridge.sent[0])

    for expected_value in range(1, 4):
        # Dispatch a real tap the way the bridge does, then let the coalesced
        # rebuild fire and the patch batch be sent.
        before = len(bridge.sent)
        await device.handle_event({"token": "1:on_click", "payload": {}})
        # Drain the loop until the new patch message has actually been sent.
        for _ in range(20):
            await asyncio.sleep(0)
            if len(bridge.sent) > before:
                break

        patch_message = bridge.sent[-1]
        assert patch_message["kind"] == "patch"
        scene = apply_patches(scene, patch_message["patches"])

        # The mirror's label text matches the new state, and the whole tree
        # matches the engine's own freshly-serialized tree.
        assert scene.root.children[0].props["content"] == f"Count: {expected_value}"
        assert _strip_event_annotations(serialize_node(scene.root)) == (
            _expected_serialized_root(device)
        )


def test_apply_patches_structural_ops() -> None:
    """Insert/remove/reorder serialized patches mutate the mirror correctly."""
    root = Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    from tempestroid import build  # noqa: PLC0415 — local import keeps top clean

    scene = deserialize_scene({"root": serialize_node(build(root)), "overlays": []})
    # insert a 'c' at index 2
    inserted = apply_patches(
        scene,
        [
            {
                "op": "insert",
                "path": [],
                "index": 2,
                "node": {
                    "type": "Text",
                    "key": "c",
                    "props": {"content": "c"},
                    "children": [],
                },
            }
        ],
    )
    assert [n.props["content"] for n in inserted.root.children] == ["a", "b", "c"]
    # reorder to c, a, b
    reordered = apply_patches(
        inserted, [{"op": "reorder", "path": [], "order": [2, 0, 1]}]
    )
    assert [n.props["content"] for n in reordered.root.children] == ["c", "a", "b"]
    # remove index 0 (c)
    removed = apply_patches(reordered, [{"op": "remove", "path": [], "index": 0}])
    assert [n.props["content"] for n in removed.root.children] == ["a", "b"]


def test_apply_update_sets_and_unsets_props() -> None:
    """An update patch sets new props and drops unset ones on the mirror node."""
    scene = deserialize_scene(
        {
            "root": {
                "type": "Text",
                "key": None,
                "props": {"content": "old", "color": "red"},
                "children": [],
            },
            "overlays": [],
        }
    )
    updated = apply_patches(
        scene,
        [{"op": "update", "path": [], "set": {"content": "new"}, "unset": ["color"]}],
    )
    assert updated.root.props == {"content": "new"}
