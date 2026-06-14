"""Unit tests for the F9 dev-server harness (server mirror + client glue).

These exercise the host↔device harness loop with no adb and no emulator: an
in-memory transport stands in for the HTTP layer, so we can prove the full path
end to end — the device's mount/patch JSON reaches the server mirror, an event
enqueued on the host is consumed by the client and fed to
``DeviceApp.handle_event``, and the resulting patch updates the mirror.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.bridge.device import DeviceApp, LoopbackBridge
from tempestroid.devserver import DevServer, HarnessTransport, poll_commands


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
    """Build a minimal counter UI.

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


def test_server_off_by_default() -> None:
    """A non-harness server ignores mount/patch and exposes no mirror."""
    server = DevServer("examples/counter/app.py")
    assert server.harness is False
    assert server.current_scene() is None
    assert server.revision() == 0


def test_server_mirror_tracks_mount_and_patch() -> None:
    """Recording a mount then a patch updates the mirror and bumps the revision."""
    server = DevServer("examples/counter/app.py", harness=True)
    assert server.harness is True
    assert server.current_scene() is None

    mount: dict[str, Any] = {
        "kind": "mount",
        "root": {
            "type": "Column",
            "key": None,
            "props": {},
            "children": [
                {
                    "type": "Text",
                    "key": "label",
                    "props": {"content": "Count: 0"},
                    "children": [],
                }
            ],
        },
        "overlays": [],
    }
    server._record_mount(mount)  # pyright: ignore[reportPrivateUsage]
    assert server.revision() == 1
    scene = server.current_scene()
    assert scene is not None
    assert scene.root.children[0].props["content"] == "Count: 0"

    server._record_patches(  # pyright: ignore[reportPrivateUsage]
        [{"op": "update", "path": [0], "set": {"content": "Count: 1"}, "unset": []}]
    )
    assert server.revision() == 2
    updated = server.current_scene()
    assert updated is not None
    assert updated.root.children[0].props["content"] == "Count: 1"


def test_server_command_queue_roundtrip() -> None:
    """Enqueued events are served FIFO and bump the consumed counter."""
    server = DevServer("examples/counter/app.py", harness=True)
    server.enqueue_event("1:on_click", {"foo": "bar"})
    server.enqueue_event("0:on_change", {"value": "x"})
    assert server.pending_commands() == 2

    first = server._next_command()  # pyright: ignore[reportPrivateUsage]
    assert first == {"token": "1:on_click", "payload": {"foo": "bar"}}
    assert server.consumed_count() == 1
    second = server._next_command()  # pyright: ignore[reportPrivateUsage]
    assert second == {"token": "0:on_change", "payload": {"value": "x"}}
    assert server.consumed_count() == 2
    assert server._next_command() is None  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_harness_transport_mirrors_and_forwards() -> None:
    """The harness transport forwards to the inner bridge and POSTs mount/patch."""
    inner = LoopbackBridge()
    posted: list[tuple[str, dict[str, Any]]] = []

    async def post(path: str, body: dict[str, Any]) -> None:
        posted.append((path, body))

    transport = HarnessTransport(inner, post)
    await transport.send({"kind": "mount", "root": {}, "overlays": []})
    await transport.send({"kind": "patch", "patches": []})

    # The inner bridge still received everything (the device renders normally).
    assert [m["kind"] for m in inner.sent] == ["mount", "patch"]
    # And mount/patch were mirrored to the right endpoints.
    assert [path for path, _ in posted] == ["/mount", "/patch"]


@pytest.mark.asyncio
async def test_end_to_end_event_through_mirror() -> None:
    """Host event → client poll → handle_event → patch → server mirror update.

    No HTTP: an in-memory ``fetch`` reads the server's ``/poll`` queue and the
    transport's ``post`` writes straight to the server's mirror. This proves the
    SAME path a real Compose tap takes drives the device app and the host mirror.
    """
    server = DevServer("examples/counter/app.py", harness=True)

    async def post(path: str, body: dict[str, Any]) -> None:
        """Mirror a mount/patch POST into the server in-process."""
        if path == "/mount":
            server._record_mount(body)  # pyright: ignore[reportPrivateUsage]
        elif path == "/patch":
            server._record_patches(  # pyright: ignore[reportPrivateUsage]
                body.get("patches", [])
            )

    # Build the device app over the harness transport so its renders mirror back.
    device: DeviceApp[CounterState] = DeviceApp(
        make_state(), view, HarnessTransport(LoopbackBridge(), post)
    )
    await device.start()
    # Drain the loop so the mount send task completes and the mirror is set.
    for _ in range(20):
        await asyncio.sleep(0)
        if server.current_scene() is not None:
            break
    scene = server.current_scene()
    assert scene is not None
    assert scene.root.children[0].props["content"] == "Count: 0"

    # The device event sink: route a polled event to handle_event (the same glue
    # run_dev_client.on_event uses, minus the unrelated reserved-token branches).
    loop = asyncio.get_running_loop()

    def sink(token: str, payload_json: str) -> None:
        payload: dict[str, Any] = json.loads(payload_json) if payload_json else {}
        message: dict[str, Any] = {
            "kind": "event",
            "token": token,
            "payload": payload,
        }
        loop.create_task(device.handle_event(message))

    # Enqueue a tap on the host, then run the poll loop once to consume it.
    server.enqueue_event("1:on_click", {})

    async def fetch(url: str) -> bytes:
        """Serve the in-memory /poll queue as JSON bytes."""
        assert url.endswith("/poll")
        command = server._next_command()  # pyright: ignore[reportPrivateUsage]
        return json.dumps(command or {"token": None}).encode("utf-8")

    await poll_commands("http://x", sink=sink, fetch=fetch, max_polls=1)
    # Let handle_event → set_state → rebuild → patch → post → mirror settle.
    for _ in range(30):
        await asyncio.sleep(0)
        current = server.current_scene()
        if current is not None and (
            current.root.children[0].props["content"] == "Count: 1"
        ):
            break

    final = server.current_scene()
    assert final is not None
    assert final.root.children[0].props["content"] == "Count: 1"
