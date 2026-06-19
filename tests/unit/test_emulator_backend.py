"""Unit tests for :class:`EmulatorBackend` with a simulated device (no adb).

The backend owns a real harness :class:`DevServer` but ``launch=False`` skips the
adb wiring, so we can stand in for the device by POSTing mount/patches and a
fake "client" that consumes enqueued events and drives a local
:class:`DeviceApp`. This proves the backend's ``scene``/``dispatch``/``settle``/
``node_at`` contract over the mirror without an emulator.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from tempestroid import App, Button, Column, Route, Text, Widget
from tempestroid.bridge.device import DeviceApp, LoopbackBridge
from tempestroid.bridge.protocol import BACK_TOKEN
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

    def __init__(
        self,
        server: Any,
        *,
        make_state_fn: Callable[[], Any] = make_state,
        view_fn: Callable[[App[Any]], Widget] = view,
    ) -> None:
        """Wire a simulated device to a harness server.

        Args:
            server: The backend's harness :class:`DevServer`.
            make_state_fn: Factory for the device app's initial state.
            view_fn: The device app's view builder.
        """
        self._server = server

        async def post(path: str, body: dict[str, Any]) -> None:
            if path == "/mount":
                server._record_mount(body)  # pyright: ignore[reportPrivateUsage]
            elif path == "/patch":
                server._record_patches(  # pyright: ignore[reportPrivateUsage]
                    body.get("patches", [])
                )

        self._device: DeviceApp[Any] = DeviceApp(
            make_state_fn(), view_fn, HarnessTransport(LoopbackBridge(), post)
        )
        self._pump_task: asyncio.Task[None] | None = None

    async def boot(self) -> None:
        """Start the device app (sends the first mount) and a command pump."""
        await self._device.start()
        self._pump_task = asyncio.get_running_loop().create_task(self._pump())

    async def _pump(self) -> None:
        """Continuously consume enqueued events into the device app.

        Mirrors the real code-push client: the reserved :data:`BACK_TOKEN` is
        routed straight to ``app.pop`` (a system back press), not fed to
        ``handle_event`` as a widget event.
        """
        while True:
            command = self._server._next_command()  # pyright: ignore[reportPrivateUsage]
            if command is not None and command.get("token"):
                token = command["token"]
                payload = command["payload"]
                if token == BACK_TOKEN:
                    self._device.app.pop()
                else:
                    await self._device.handle_event(
                        {"kind": "event", "token": token, "payload": payload}
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


def _nav_state() -> CounterState:
    """Build a fresh state for the navigation back() test.

    Returns:
        A new state (nav depth lives in ``app.nav``, not here).
    """
    return CounterState()


def _nav_view(app: App[CounterState]) -> Widget:
    """Build a view that pushes onto ``app.nav`` and shows the top route.

    Args:
        app: The running app.

    Returns:
        The root widget exposing the current route name and a push button.
    """
    return Column(
        children=[
            Text(content=f"route: {app.nav.top.name}", key="route"),
            Button(
                label="push",
                key="push",
                on_click=lambda: app.push(Route(name="/stack/1")),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_emulator_back_pops_the_nav_stack(tmp_path: Any) -> None:
    """``page.back()`` routes the reserved back token → device ``app.pop``.

    Proves the F9 emulator-backend back() gap is closed: a push deepens the real
    device app's nav stack, and a back() (the same envelope the Android back
    button rides) pops it, reflected in the host-side mirror.
    """
    app_file = tmp_path / "app.py"
    app_file.write_text("def view(app): ...\ndef make_state(): ...\n")

    backend = EmulatorBackend(app_file, "emulator-test", launch=False)
    from tempestroid.devserver import DevServer

    backend._server = DevServer(  # pyright: ignore[reportPrivateUsage]
        app_file, host="127.0.0.1", port=0, log=lambda _l: None, harness=True
    )
    backend._server.start()  # pyright: ignore[reportPrivateUsage]
    device = _SimulatedDevice(
        backend._server,  # pyright: ignore[reportPrivateUsage]
        make_state_fn=_nav_state,
        view_fn=_nav_view,
    )
    await device.boot()

    page = Page(backend)
    await backend._await_first_mount()  # pyright: ignore[reportPrivateUsage]
    backend._mounted = True  # pyright: ignore[reportPrivateUsage]

    try:
        await page.expect_text("route: /")
        await page.tap(page.get_by_key("push"))
        await page.expect_text("route: /stack/1")
        await page.back()
        await page.expect_text("route: /")
    finally:
        device.stop()
        backend.close()
