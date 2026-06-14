"""Unit tests for :class:`EmulatorBackend` with a simulated device (no adb).

The backend owns a real harness :class:`DevServer` but ``launch=False`` skips the
adb wiring, so we can stand in for the device by POSTing mount/patches and a
fake "client" that consumes enqueued events and drives a local
:class:`DeviceApp`. This proves the backend's ``scene``/``dispatch``/``settle``/
``node_at`` contract over the mirror without an emulator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.bridge.device import DeviceApp, LoopbackBridge
from tempestroid.devserver import HarnessTransport
from tempestroid.testing import EmulatorBackend, Page


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


class _SimulatedDevice:
    """A fake on-device client: mirrors renders to the backend's server.

    Drives a real :class:`DeviceApp` over a :class:`HarnessTransport` whose POSTs
    are applied straight to the backend's server, and consumes enqueued events
    into ``handle_event`` — exactly what the real code-push client does, but in
    the same process and with no HTTP/adb.
    """

    def __init__(self, server: Any) -> None:
        """Wire a simulated device to a harness server.

        Args:
            server: The backend's harness :class:`DevServer`.
        """
        self._server = server

        async def post(path: str, body: dict[str, Any]) -> None:
            if path == "/mount":
                server._record_mount(body)  # pyright: ignore[reportPrivateUsage]
            elif path == "/patch":
                server._record_patches(  # pyright: ignore[reportPrivateUsage]
                    body.get("patches", [])
                )

        self._device: DeviceApp[CounterState] = DeviceApp(
            make_state(), view, HarnessTransport(LoopbackBridge(), post)
        )
        self._pump_task: asyncio.Task[None] | None = None

    async def boot(self) -> None:
        """Start the device app (sends the first mount) and a command pump."""
        await self._device.start()
        self._pump_task = asyncio.get_running_loop().create_task(self._pump())

    async def _pump(self) -> None:
        """Continuously consume enqueued events into the device app."""
        while True:
            command = self._server._next_command()  # pyright: ignore[reportPrivateUsage]
            if command is not None and command.get("token"):
                payload = command["payload"]
                await self._device.handle_event(
                    {"kind": "event", "token": command["token"], "payload": payload}
                )
            await asyncio.sleep(0.01)

    def stop(self) -> None:
        """Cancel the command pump."""
        if self._pump_task is not None:
            self._pump_task.cancel()


@pytest.mark.asyncio
async def test_emulator_backend_drives_real_app_over_mirror(tmp_path: Any) -> None:
    """Mount → tap → settle → assert works against the simulated device."""
    app_file = tmp_path / "app.py"
    app_file.write_text("def view(app): ...\ndef make_state(): ...\n")

    backend = EmulatorBackend(app_file, "emulator-test", launch=False)
    # Start the server but stand in for the adb-launched client.
    from tempestroid.devserver import DevServer

    backend._server = DevServer(  # pyright: ignore[reportPrivateUsage]
        app_file, host="127.0.0.1", port=0, log=lambda _l: None, harness=True
    )
    backend._server.start()  # pyright: ignore[reportPrivateUsage]
    device = _SimulatedDevice(backend._server)  # pyright: ignore[reportPrivateUsage]
    await device.boot()

    page = Page(backend)
    # mount() would normally serve + adb; here just await the first mirror.
    await backend._await_first_mount()  # pyright: ignore[reportPrivateUsage]
    backend._mounted = True  # pyright: ignore[reportPrivateUsage]

    try:
        await page.expect_text("Count: 0")
        await page.tap(page.get_by_key("inc"))
        await page.expect_text("Count: 1")
        await page.tap(page.get_by_key("inc"))
        await page.expect_text("Count: 2")
        # The backend resolves the handler to a TOKEN, not a callable.
        node = page.get_by_key("inc").first
        assert node.props["on_click"]["$handler"] == "1:on_click"
    finally:
        device.stop()
        backend.close()


def test_patches_returns_empty_list(tmp_path: Any) -> None:
    """The emulator backend mirrors serialized patches; ``patches()`` is []."""
    backend = EmulatorBackend(tmp_path / "app.py", "emulator-test", launch=False)
    assert backend.patches() == []


def test_scene_before_mount_raises(tmp_path: Any) -> None:
    """``scene()`` before any mount raises a clear error."""
    backend = EmulatorBackend(tmp_path / "app.py", "emulator-test", launch=False)
    with pytest.raises(RuntimeError, match="no mirrored scene"):
        backend.scene()
