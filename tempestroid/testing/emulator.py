"""The emulator/device :class:`TestBackend` — drive a REAL app on Android.

:class:`EmulatorBackend` is the third implementation of
:class:`~tempestroid.testing.backend.TestBackend` (after the headless and Qt
backends). It runs the *same* Page/Locator test script against an app actually
rendering through the **Compose** renderer on an x86_64 (or arm64) Android
emulator/device — so a passing emulator test is proof the real device leaf
behaves like the headless core.

Transport (the F9 decision — no C/JNI change, no ``adb input tap``):

* The backend owns an in-process :class:`~tempestroid.devserver.DevServer` in
  **harness mode** and ``adb -s <serial> reverse``-s the device's localhost to
  it, then launches the prebuilt host in dev mode pointed at the server.
* device → host: the device's code-push client POSTs the serialized mount JSON
  and every patch batch back; the dev server keeps a host-side
  :class:`~tempest_core.core.ir.Scene` **mirror** (via
  :mod:`tempestroid.testing.mirror`). :meth:`scene` returns that mirror.
* host → device: :meth:`dispatch` reads the handler **token** from the mirror
  node's prop (``{"$handler": token}``), enqueues ``{token, payload}`` on the
  server; the client long-polls, picks it up, and feeds it to
  ``DeviceApp.handle_event`` — the *same* sink path a real Compose tap takes. The
  rebuild → patch flows back and updates the mirror.

Auto-wait (:meth:`settle`) polls the mirror **revision** until it has been quiet
for a short window *and* any in-flight enqueued event has been consumed — never a
fixed sleep as the primary mechanism — bounded by a timeout.

.. note::
   The headless backend resolves a node's handler prop to a real **callable**;
   the emulator backend resolves it to a **token string** (the callable lives on
   the device). Both satisfy the identical :class:`TestBackend` protocol, so
   ``Page``/``Locator``/``expect_*`` are unchanged across targets.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from tempest_core.core.ir import Node, Patch, Scene

from tempestroid.bridge.protocol import BACK_TOKEN
from tempestroid.testing.tree import node_at

if TYPE_CHECKING:
    from tempestroid.devserver import DevServer

__all__ = ["EmulatorBackend"]

#: Default seconds :meth:`EmulatorBackend.settle` waits for the mirror to go
#: quiet before raising — generous, since it returns the instant the tree is
#: stable, not after a fixed sleep.
_DEFAULT_SETTLE_TIMEOUT = 30.0

#: Seconds the mirror revision must stay unchanged (and no command in flight)
#: for :meth:`settle` to consider the tree settled.
_QUIET_WINDOW = 0.4

#: Seconds :meth:`mount` waits for the device's first mount POST to arrive.
_MOUNT_TIMEOUT = 120.0

#: The host activity launched in dev mode (mirrors
#: :data:`tempestroid.cli.packaging._HOST_ACTIVITY`).
_HOST_ACTIVITY = "org.tempestroid.host/.MainActivity"
#: The host package id (the part of :data:`_HOST_ACTIVITY` before ``/``), used to
#: force-stop a still-running host before each per-test launch.
_HOST_PACKAGE = _HOST_ACTIVITY.split("/", 1)[0]
_DEV_URL_EXTRA = "tempest_dev_url"
#: After a dispatched event is consumed, wait at most this long for its rebuild
#: patch (a revision bump) before treating the event as a no-op and settling —
#: so ``settle`` provably waits for the device's round-trip when one is coming.
_SETTLE_GRACE = 2.0


class EmulatorBackend:
    """Drive a real Compose-rendered app on an emulator over the dev-server bridge.

    Methods:
        mount: Serve the app, wire the device, and await the first mounted scene.
        scene: Return the host-side mirror of the device's live scene.
        dispatch: Enqueue a typed event at a node's handler token, then settle.
        back: Enqueue the reserved back token (device pop), then settle.
        settle: Auto-wait until the mirror is quiet (no fixed sleep primary path).
        patches: Return every patch batch the device sent since mount.
        node_at: Resolve a node by its IR path in the mirror.
        screenshot: Capture REAL Compose pixels via ``adb exec-out screencap``.
        close: Stop the dev server and drop the ``adb reverse`` (best-effort).
    """

    def __init__(
        self,
        app_path: str | Path,
        serial: str,
        *,
        port: int = 0,
        adb: str = "adb",
        launch: bool = True,
    ) -> None:
        """Initialize the backend bound to one emulator/device serial.

        Args:
            app_path: Path to the app file (or project entry) to serve.
            serial: The ``adb`` serial of the target emulator/device
                (e.g. ``"emulator-5554"``).
            port: The dev-server TCP port; ``0`` picks a free one.
            adb: The ``adb`` executable name/path.
            launch: Auto ``adb reverse`` + launch the host in dev mode on
                :meth:`mount`. Set ``False`` when the host is already running in
                dev mode against this server (tests/manual).
        """
        self._app_path = Path(app_path).resolve()
        self._serial = serial
        self._port: int = port
        self._adb = adb
        self._launch = launch
        # DevServer (lazily imported to avoid a cycle); typed via TYPE_CHECKING.
        self._server: DevServer | None = None
        self._mounted = False

    @property
    def serial(self) -> str:
        """The bound emulator/device serial.

        Returns:
            The ``adb`` serial string.
        """
        return self._serial

    def _require_server(self) -> DevServer:
        """Return the harness dev server, asserting it has been started.

        Returns:
            The running :class:`~tempestroid.devserver.DevServer`.

        Raises:
            RuntimeError: If accessed before :meth:`mount` started the server.
        """
        if self._server is None:
            raise RuntimeError("backend not mounted — call await page.mount() first")
        return self._server

    async def mount(self) -> None:
        """Serve the app, wire the device, and await the first mounted scene.

        Starts the in-process harness dev server, ``adb reverse``-s the device's
        localhost to it, launches the prebuilt host in dev mode (unless
        ``launch=False``), and blocks until the device POSTs its first mount (the
        mirror becomes non-empty). Idempotent.

        Raises:
            TimeoutError: If no mount arrives within :data:`_MOUNT_TIMEOUT`.
        """
        if self._mounted:
            return
        from tempestroid.devserver import DevServer

        self._server = DevServer(
            self._app_path,
            host="127.0.0.1",
            port=self._port,
            log=lambda _line: None,
            harness=True,
        )
        self._server.start()
        self._port = int(self._server.port)
        if self._launch:
            # adb + am are blocking; keep the event loop responsive.
            await asyncio.to_thread(self._adb_reverse, self._port)
            await asyncio.to_thread(self._launch_host, self._port)
        await self._await_first_mount()
        self._mounted = True

    def scene(self) -> Scene:
        """Return the host-side mirror of the device's live scene.

        Returns:
            The mirrored :class:`~tempest_core.core.ir.Scene`.

        Raises:
            RuntimeError: If the device has not yet mounted.
        """
        scene = self._server.current_scene() if self._server is not None else None
        if scene is None:
            raise RuntimeError(
                "no mirrored scene yet — call await page.mount() first (the device "
                "has not POSTed a mount)"
            )
        return scene

    async def dispatch(
        self, node: Node, handler_name: str, payload: Mapping[str, Any]
    ) -> None:
        """Enqueue a typed event at a node's handler token, then auto-wait.

        Reads the handler **token** from ``node.props[handler_name]`` (which on a
        mirror node is ``{"$handler": token}``), enqueues ``{token, payload}`` on
        the harness dev server for the device to consume, and settles.

        Args:
            node: The target mirror node carrying the handler ref in its props.
            handler_name: The handler prop name (e.g. ``"on_click"``).
            payload: The raw event payload (validated device-side on dispatch).

        Raises:
            KeyError: If the node carries no handler token under ``handler_name``.
            TimeoutError: If the tree does not settle after the event runs.
        """
        token = _handler_token(node, handler_name)
        server = self._require_server()
        before = server.consumed_count()
        server.enqueue_event(token, dict(payload))
        await self.settle(consumed_floor=before + 1)

    async def back(self) -> None:
        """Fire a system back action on the device, then auto-wait to settle.

        Enqueues the reserved :data:`~tempestroid.bridge.protocol.BACK_TOKEN`
        on the harness dev server — the *same* envelope the device's own back
        button rides. The code-push client picks it up and routes it straight to
        ``DeviceApp.app.pop`` (see :mod:`tempestroid.devserver.client`), so the
        pop runs on the real Compose-rendered app and the resulting patch flows
        back into the mirror. No C/JNI change: back reuses the event channel.

        Raises:
            TimeoutError: If the tree does not settle after the back runs.
        """
        server = self._require_server()
        before = server.consumed_count()
        server.enqueue_event(BACK_TOKEN, {})
        await self.settle(consumed_floor=before + 1)

    async def settle(
        self,
        timeout: float = _DEFAULT_SETTLE_TIMEOUT,
        *,
        consumed_floor: int | None = None,
    ) -> None:
        """Auto-wait until the mirror is quiet, bounded by ``timeout``.

        Polls the mirror revision (and the command queue). The tree is "settled"
        when, for a short quiet window, the revision has not changed, no command
        is queued, and — if ``consumed_floor`` is given — the client has consumed
        at least that many commands (so an enqueued event provably reached the
        device before we conclude it produced no change). Never a fixed sleep as
        the primary mechanism: the wait ends the instant those conditions hold.

        Args:
            timeout: Maximum seconds to wait before raising.
            consumed_floor: Minimum consumed-command count required before the
                tree can be considered settled (set by :meth:`dispatch`).

        Raises:
            TimeoutError: If the tree has not settled within ``timeout``.
        """
        server = self._require_server()
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        baseline_revision = server.revision()
        last_revision = baseline_revision
        quiet_since = loop.time()
        consumed_at: float | None = None
        while True:
            await asyncio.sleep(0.05)
            now = loop.time()
            revision = server.revision()
            pending = server.pending_commands()
            consumed_ok = (
                consumed_floor is None or server.consumed_count() >= consumed_floor
            )
            if consumed_ok and consumed_at is None:
                consumed_at = now
            if revision != last_revision:
                last_revision = revision
                quiet_since = now
            # The dispatched event's effect is the rebuild patch: a revision bump
            # after the command was consumed. Don't conclude "settled" until we've
            # seen it — unless the grace elapses with none (a no-op handler).
            saw_patch = revision != baseline_revision
            effect_resolved = saw_patch or (
                consumed_at is not None and (now - consumed_at) >= _SETTLE_GRACE
            )
            quiet_long_enough = (now - quiet_since) >= _QUIET_WINDOW
            if pending == 0 and consumed_ok and effect_resolved and quiet_long_enough:
                return
            if now >= deadline:
                raise TimeoutError(
                    f"emulator tree did not settle within {timeout:.1f}s on "
                    f"{self._serial} (pending commands: {pending}, consumed_ok: "
                    f"{consumed_ok}). The device may not be running the host in "
                    "dev/harness mode against this server."
                )

    def patches(self) -> list[Patch]:
        """Return the recorded patch batches.

        The emulator backend mirrors *serialized* patches into a host-side
        :class:`Scene`; it does not retain the live :class:`Patch` objects (those
        are applied on the device). This returns an empty list — assertions use
        :meth:`scene` (the mirror), which is the cross-renderer source of truth.

        Returns:
            An empty list (see the note above).
        """
        return []

    def node_at(self, path: tuple[int | str, ...]) -> Node:
        """Resolve a node by its IR path in the mirror.

        Args:
            path: The node address.

        Returns:
            The node at ``path``.

        Raises:
            KeyError: If the path does not resolve.
        """
        return node_at(self.scene(), path)

    def screenshot(self, path: str | Path) -> Path:
        """Capture the REAL Compose render to a PNG via ``adb screencap``.

        These are genuine on-device Compose pixels — the clarity deliverable that
        the headless backend cannot produce.

        Args:
            path: Destination PNG path; parent dirs are created.

        Returns:
            The written path.

        Raises:
            subprocess.CalledProcessError: If the ``adb`` capture fails.
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(  # noqa: S603
            [self._adb, "-s", self._serial, "exec-out", "screencap", "-p"],
            check=True,
            capture_output=True,
        )
        stdout: bytes = result.stdout
        dest.write_bytes(stdout)
        return dest

    def close(self) -> None:
        """Stop the dev server and drop the ``adb reverse`` (best-effort)."""
        if self._server is not None:
            self._server.stop()
            self._server = None
        try:
            subprocess.run(  # noqa: S603
                [
                    self._adb,
                    "-s",
                    self._serial,
                    "reverse",
                    "--remove",
                    f"tcp:{self._port}",
                ],
                check=False,
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    async def _await_first_mount(self) -> None:
        """Block until the device POSTs its first mount or the timeout elapses.

        Raises:
            TimeoutError: If no mount arrives in time.
        """
        server = self._require_server()
        loop = asyncio.get_event_loop()
        deadline = loop.time() + _MOUNT_TIMEOUT
        while server.current_scene() is None:
            await asyncio.sleep(0.1)
            if loop.time() >= deadline:
                raise TimeoutError(
                    f"no mount from {self._serial} within {_MOUNT_TIMEOUT:.0f}s. "
                    "Is the host installed and able to reach the dev server "
                    "(adb reverse + dev mode)?"
                )

    def _adb_reverse(self, port: int) -> None:
        """Wire ``adb -s <serial> reverse`` for this device's localhost.

        Args:
            port: The dev-server port.
        """
        subprocess.run(  # noqa: S603
            [self._adb, "-s", self._serial, "reverse", f"tcp:{port}", f"tcp:{port}"],
            check=True,
        )

    def _launch_host(self, port: int) -> None:
        """Launch the prebuilt host on this device in dev mode.

        Args:
            port: The dev-server port the host's code-push client targets.
        """
        # Pre-grant POST_NOTIFICATIONS: on a fresh/cleared install the system
        # permission dialog (GrantPermissionsActivity) steals focus from
        # MainActivity and blocks the first Compose mount, flaking the run.
        # Best-effort — fails harmlessly on APIs that don't gate it.
        subprocess.run(  # noqa: S603
            [
                self._adb,
                "-s",
                self._serial,
                "shell",
                "pm",
                "grant",
                _HOST_PACKAGE,
                "android.permission.POST_NOTIFICATIONS",
            ],
            check=False,
            capture_output=True,
        )
        # Force-stop first: `am start` on an already-running host only delivers a
        # new-intent to the live instance, whose dev-client keeps polling the
        # previous (now-closed) server port and never re-mounts. Stopping it makes
        # every per-test launch a cold start that connects to THIS server.
        subprocess.run(  # noqa: S603
            [self._adb, "-s", self._serial, "shell", "am", "force-stop", _HOST_PACKAGE],
            check=True,
        )
        subprocess.run(  # noqa: S603
            [
                self._adb,
                "-s",
                self._serial,
                "shell",
                "am",
                "start",
                "-n",
                _HOST_ACTIVITY,
                "--es",
                _DEV_URL_EXTRA,
                f"http://127.0.0.1:{port}",
            ],
            check=True,
        )


def _handler_token(node: Node, handler_name: str) -> str:
    """Read the handler token from a mirror node's prop.

    On a mirror node a handler prop is the serialized ref ``{"$handler": token,
    "event": ...}`` (the callable lives on the device). This pulls the token out.

    Args:
        node: The mirror node.
        handler_name: The handler prop name.

    Returns:
        The handler token string.

    Raises:
        KeyError: If the node has no handler ref under ``handler_name``.
    """
    ref: object = node.props.get(handler_name)
    if isinstance(ref, Mapping):
        ref_map = cast("Mapping[str, object]", ref)
        if "$handler" in ref_map:
            return str(ref_map["$handler"])
    raise KeyError(
        f"node {node.type!r} has no handler token {handler_name!r} "
        f"(props: {sorted(node.props)}). On the emulator backend a handler "
        "prop must be a serialized handler ref carrying a $handler token."
    )
