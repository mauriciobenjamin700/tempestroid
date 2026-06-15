"""Wire an ``App`` to a device over an abstract transport.

``DeviceApp`` is the device-side analogue of ``run_qt``: it owns an ``App`` plus a
:class:`HandlerRegistry`, serializes the initial tree and every patch batch onto
a :class:`Bridge`, and feeds incoming events back through the registry (which may
call ``app.set_state`` and trigger another patch batch).

The :class:`Bridge` is transport-agnostic. The real device transport is the JNI
shim (phase B3, Kotlin side); :class:`LoopbackBridge` is an in-memory transport
for tests and local wiring.
"""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from tempest_core.core.ir import Patch
from tempest_core.core.state import App
from tempest_core.navigation import NavStack
from tempest_core.widgets import Widget

from tempestroid.bridge.handlers import HandlerRegistry
from tempestroid.bridge.protocol import (
    DISMISS_TOKEN_PREFIX,
    EventMessage,
    MountMessage,
    PatchMessage,
)
from tempestroid.bridge.serializer import serialize_node, serialize_patch

__all__ = ["Bridge", "LoopbackBridge", "DeviceApp"]

S = TypeVar("S")


class Bridge(abc.ABC):
    """A transport that carries serialized messages to the device."""

    @abc.abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send one serialized message to the device.

        Args:
            message: A JSON-able message dict (``mount`` / ``patch``).
        """
        raise NotImplementedError


class LoopbackBridge(Bridge):
    """In-memory bridge that records sent messages (for tests/local wiring)."""

    def __init__(self) -> None:
        """Create a loopback bridge with an empty outbox."""
        self.sent: list[dict[str, Any]] = []

    async def send(self, message: dict[str, Any]) -> None:
        """Record a sent message.

        Args:
            message: The message dict.
        """
        self.sent.append(message)


class DeviceApp(Generic[S]):
    """Runs an ``App`` against a device :class:`Bridge`.

    Type Args:
        S: The application state type.
    """

    def __init__(
        self,
        state: S,
        view: Callable[[App[S]], Widget],
        bridge: Bridge,
        nav: NavStack | None = None,
    ) -> None:
        """Initialize the device app.

        Args:
            state: The initial application state.
            view: Builds the widget tree from the app.
            bridge: The transport to the device.
            nav: The initial navigation stack (e.g. from a deep link resolved on
                boot). Defaults to a fresh stack with the root route.
        """
        self._bridge: Bridge = bridge
        self._registry: HandlerRegistry = HandlerRegistry()
        self._app: App[S] = App(state, view, apply_patches=self._on_patches, nav=nav)
        # Strong refs to in-flight send tasks so the loop does not GC them.
        self._pending: set[asyncio.Task[None]] = set()

    @property
    def app(self) -> App[S]:
        """The wrapped app.

        Returns:
            The app.
        """
        return self._app

    async def start(self) -> None:
        """Build the initial scene, register handlers, and send the mount message."""
        scene = self._app.start()
        self._registry.refresh(scene)
        await self._bridge.send(
            MountMessage(
                root=serialize_node(scene.root),
                overlays=[
                    serialize_node(overlay, ("overlay", index))
                    for index, overlay in enumerate(scene.overlays)
                ],
                can_pop=self._app.nav.can_pop,
                has_animations=self._app.has_animations,
                theme_mode=self._app.theme.mode.value,
            ).model_dump()
        )

    def reload(self, view: Callable[[App[S]], Widget]) -> None:
        """Hot-reload the view, preserving state and patching the device.

        Swaps the running app's view via :meth:`App.swap_view` (which diffs the
        new tree against the live one and pushes the resulting patch batch over
        the bridge through :meth:`_on_patches`), then refreshes the handler
        registry so taps resolve against the reloaded closures even when the tree
        was structurally unchanged.

        Args:
            view: The reloaded view function.

        Raises:
            Exception: Whatever the new view/build raises — the swap is rolled
                back. The caller (code-push client) falls back to a clean restart.
        """
        self._app.swap_view(view)
        self._registry.refresh(self._app.current_tree)

    async def handle_event(self, message: dict[str, Any]) -> None:
        """Process an event coming back from the device.

        A token with the reserved :data:`DISMISS_TOKEN_PREFIX` (an overlay
        dismissed by a host-owned gesture) is routed straight to
        :meth:`~tempestroid.core.state.App.dismiss`; every other token is a
        widget handler, validated and dispatched via the registry. Either path's
        resulting ``set_state``/``dismiss`` schedules a coalesced rebuild whose
        patches are sent on the next tick.

        Args:
            message: A serialized :class:`EventMessage` dict.
        """
        event = EventMessage.model_validate(message)
        prefix = f"{DISMISS_TOKEN_PREFIX}:"
        if event.token.startswith(prefix):
            self._app.dismiss(event.token[len(prefix) :])
            return
        await self._registry.dispatch(event.token, event.payload)

    def _on_patches(self, patches: list[Patch]) -> None:
        """Refresh handlers from the new tree and send the patch batch.

        Called by ``App`` after a rebuild (sync, on the loop). The send is
        scheduled as a task since the bridge is async.

        Args:
            patches: The patches produced by the reconciler.
        """
        self._registry.refresh(self._app.current_tree)
        message = PatchMessage(
            patches=[serialize_patch(p) for p in patches],
            can_pop=self._app.nav.can_pop,
            has_animations=self._app.has_animations,
            theme_mode=self._app.theme.mode.value,
        ).model_dump()
        task = asyncio.get_running_loop().create_task(self._bridge.send(message))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
