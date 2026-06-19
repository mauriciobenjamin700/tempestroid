"""Test backends: the seam that lets one driver target many renderers.

A :class:`TestBackend` is the only renderer-specific surface the driver touches.
It mounts an app, exposes the **built IR** (the :class:`~tempestroid.core.ir.Scene`
the reconciler produces and both leaf renderers realize), injects a typed event
the way a real tap/keystroke would, and — crucially — **auto-waits** for the tree
to settle before any action or assertion proceeds. Because every backend speaks
the same IR + typed-event vocabulary, the same test script runs against every one.

This slice ships the **headless** backend only: :class:`HeadlessBackend` drives an
:class:`~tempestroid.core.state.App` in-process with no renderer at all, so a test
exercises the full ``event → handler → state → coalesced rebuild → diff → patch``
loop deterministically and fast. A Qt-window backend (in-process ``QWidget``s) and
emulator/device backends (over the ``dispatchEvent`` ↔ mount/patch bridge) slot in
behind this same protocol once Trilho F8 lands the stable targets — they only need
to satisfy :class:`TestBackend`; the :class:`~tempestroid.testing.Page` /
:class:`~tempestroid.testing.Locator` / assertion layer is unchanged.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from tempest_core.core.ir import Node, Patch, Path, Scene
from tempest_core.core.state import App
from tempest_core.widgets import Widget
from tempest_core.widgets.base import handler_accepts_event
from tempest_core.widgets.events import Event, TapEvent, TextChangeEvent, parse_event

from tempestroid.testing.tree import node_at

__all__ = ["TestBackend", "HeadlessBackend", "event_schema_for"]

#: How long :meth:`HeadlessBackend.settle` waits for the tree to stop changing
#: before giving up, in seconds. Generous, since the wait ends the instant the
#: tree is stable (it is not a fixed sleep).
_DEFAULT_SETTLE_TIMEOUT = 5.0

#: Value-bearing handler names that fall back to :class:`TextChangeEvent` when a
#: node's widget type declares no schema (a bare callable); everything else
#: falls back to :class:`TapEvent`.
_VALUE_HANDLER_NAMES = frozenset({"on_change", "on_input", "on_text"})


def _build_schema_index() -> dict[str, dict[str, type[Event]]]:
    """Index every widget's ``event_schemas`` by widget type name.

    Walks the :class:`~tempestroid.widgets.Widget` subclass tree (the registry
    is implicit in Python's class hierarchy) and collects each class's declared
    ``event_schemas`` classvar, so a built node — which only carries its type
    name as a string — can be mapped back to the typed event a given handler
    expects. Later subclasses win on a name clash (none exist today).

    Returns:
        A mapping ``{widget_type_name: {handler_prop_name: Event subclass}}``.
    """
    index: dict[str, dict[str, type[Event]]] = {}

    def visit(cls: type[Widget]) -> None:
        schemas = getattr(cls, "event_schemas", {})
        if schemas:
            index.setdefault(cls.__name__, {}).update(schemas)
        for sub in cls.__subclasses__():
            visit(sub)

    visit(Widget)
    return index


#: Built once at import time: ``{widget_type_name: {handler_name: Event class}}``.
_SCHEMA_INDEX: dict[str, dict[str, type[Event]]] = _build_schema_index()


def event_schema_for(node_type: str, handler_name: str) -> type[Event]:
    """Resolve the typed event a node's handler expects.

    Looks the node's widget type up in the schema index; falls back to
    :class:`TextChangeEvent` for value-bearing handler names and
    :class:`TapEvent` otherwise, so even a bare/unknown handler dispatches a
    sensible typed payload.

    Args:
        node_type: The node's ``type`` tag (e.g. ``"Button"``).
        handler_name: The handler prop name (e.g. ``"on_click"``).

    Returns:
        The :class:`~tempestroid.widgets.events.Event` subclass to validate the
        payload into.
    """
    schemas = _SCHEMA_INDEX.get(node_type, {})
    if handler_name in schemas:
        return schemas[handler_name]
    if handler_name in _VALUE_HANDLER_NAMES:
        return TextChangeEvent
    return TapEvent


@runtime_checkable
class TestBackend(Protocol):
    """The renderer-specific surface the driver automates.

    A backend mounts an app, exposes its built scene, injects typed events, and
    auto-waits for the tree to settle. Every method an action or assertion needs
    is here; the :class:`~tempestroid.testing.Page` layer above it is fully
    renderer-agnostic. Implement this protocol to add a target (a Qt-window or
    emulator/device backend lands behind it with Trilho F8).

    Methods:
        mount: Build and mount the app, recording the initial scene.
        scene: Return the current built scene.
        dispatch: Inject a typed event at a node's handler, then settle.
        back: Fire a system back action (pop the navigation stack), then settle.
        settle: Auto-wait until the tree stops changing (no fixed sleep).
        patches: Return every patch batch applied since mount (newest last).
    """

    async def mount(self) -> None:
        """Build and mount the app, recording the initial scene."""
        ...

    def scene(self) -> Scene:
        """Return the current built scene (the live IR).

        Returns:
            The current :class:`~tempestroid.core.ir.Scene`.
        """
        ...

    async def dispatch(
        self, node: Node, handler_name: str, payload: Mapping[str, Any]
    ) -> None:
        """Inject a typed event at a node's handler, then auto-wait to settle.

        Args:
            node: The target node carrying the handler in its props.
            handler_name: The handler prop name (e.g. ``"on_click"``).
            payload: The raw event payload, validated into a typed event.
        """
        ...

    async def back(self) -> None:
        """Fire a system back action (pop the navigation stack), then settle.

        The renderer-agnostic analogue of an Android back press: it pops the
        framework navigation stack the same way the platform back button does
        (headless pops the in-process app; the emulator routes the reserved
        back token to the device), then auto-waits for the rebuild to settle.
        """
        ...

    async def settle(self, timeout: float = _DEFAULT_SETTLE_TIMEOUT) -> None:
        """Auto-wait until the tree stops changing or ``timeout`` elapses.

        Args:
            timeout: Maximum seconds to wait before raising.

        Raises:
            TimeoutError: If the tree has not settled within ``timeout``.
        """
        ...

    def patches(self) -> list[Patch]:
        """Return every patch applied since mount, in application order.

        Returns:
            The flattened list of applied patches.
        """
        ...


class HeadlessBackend:
    """Drive an :class:`~tempestroid.core.state.App` in-process, no renderer.

    The reference backend: it wires an :class:`App` to a recording
    ``apply_patches`` callback, builds the scene via :meth:`App.start`, and runs
    the real coalesced-rebuild loop on the ambient asyncio loop. Actions inject
    the same typed events a renderer would, so a test exercises the genuine
    ``event → handler → state → rebuild → diff → patch`` path with zero UI — fast
    and deterministic.

    Auto-wait (:meth:`settle`) is the headless analogue of Playwright's: it
    yields to the loop until no rebuild is pending **and** two consecutive scene
    snapshots are equal, never a fixed sleep, so timing flake cannot creep in.

    Methods:
        mount: Build and mount the app, recording the initial scene.
        scene: Return the current built scene.
        dispatch: Inject a typed event at a node's handler, then settle.
        back: Pop the in-process navigation stack, then settle.
        settle: Auto-wait until the tree stops changing (no fixed sleep).
        patches: Return every applied patch in order.
        node_at: Resolve a node by its IR path in the current scene.
    """

    def __init__(
        self,
        make_state: Callable[[], Any],
        view: Callable[[App[Any]], Widget],
    ) -> None:
        """Initialize the backend with an app's entry points.

        Args:
            make_state: Factory returning a fresh initial state.
            view: Builds the widget tree from the running app.
        """
        self._make_state = make_state
        self._view = view
        self._patches: list[Patch] = []
        self._app: App[Any] | None = None
        self._mounted = False

    @property
    def app(self) -> App[Any]:
        """The underlying app (after :meth:`mount`).

        Returns:
            The running :class:`App`.

        Raises:
            RuntimeError: If accessed before :meth:`mount`.
        """
        if self._app is None:
            raise RuntimeError("backend not mounted — call await page.mount() first")
        return self._app

    async def mount(self) -> None:
        """Build and mount the app, recording the initial scene.

        Constructs a fresh :class:`App` over a recording ``apply_patches`` and
        calls :meth:`App.start`, so the current scene is available immediately.
        Idempotent: a second call is a no-op.
        """
        if self._mounted:
            return
        self._app = App(self._make_state(), self._view, self._record_patches)
        self._app.start()
        self._mounted = True

    def scene(self) -> Scene:
        """Return the current built scene (the live IR).

        Returns:
            The current :class:`~tempestroid.core.ir.Scene`.

        Raises:
            RuntimeError: If the app has not been mounted/started.
        """
        tree = self.app.current_tree
        if tree is None:
            raise RuntimeError(
                "app has no current tree — call await page.mount() first"
            )
        return tree

    async def dispatch(
        self, node: Node, handler_name: str, payload: Mapping[str, Any]
    ) -> None:
        """Inject a typed event at a node's handler, then auto-wait to settle.

        Resolves the raw callable from the node's props, validates ``payload``
        into the typed event the widget declares for ``handler_name`` (via
        :func:`event_schema_for`), calls the handler arity-aware (passing the
        event only when it accepts one), awaits a coroutine result, and finally
        settles the tree.

        Args:
            node: The target node carrying the handler in its props.
            handler_name: The handler prop name (e.g. ``"on_click"``).
            payload: The raw event payload, validated into a typed event.

        Raises:
            KeyError: If the node carries no handler under ``handler_name``.
            EventValidationError: If ``payload`` fails validation.
            TimeoutError: If the tree does not settle after the handler runs.
        """
        handler = node.props.get(handler_name)
        if not callable(handler):
            raise KeyError(
                f"node {node.type!r} has no callable handler {handler_name!r} "
                f"(props: {sorted(node.props)})"
            )
        event: Event = parse_event(event_schema_for(node.type, handler_name), payload)
        result: Any
        if handler_accepts_event(handler):
            result = handler(event)
        else:
            result = handler()
        if inspect.iscoroutine(result):
            await result
        await self.settle()

    async def back(self) -> None:
        """Pop the in-process navigation stack, then auto-wait to settle.

        Calls :meth:`~tempestroid.core.state.App.pop` directly — the headless
        analogue of an Android back press — and settles the resulting rebuild.
        A pop at the root route is a no-op (the app guards it), matching the
        device, so the call is always safe.
        """
        self.app.pop()
        await self.settle()

    async def settle(self, timeout: float = _DEFAULT_SETTLE_TIMEOUT) -> None:
        """Auto-wait until the tree stops changing or ``timeout`` elapses.

        Loops yielding to the event loop (``await asyncio.sleep(0)``, never a
        fixed delay) until both: no rebuild is pending on the app, and two
        consecutive scene snapshots compare equal. This drains the coalesced
        rebuild queue and any handler-scheduled ``call_soon`` work, so an action
        only returns once the UI is stable.

        Args:
            timeout: Maximum seconds to wait before raising.

        Raises:
            TimeoutError: If the tree has not settled within ``timeout``, with
                the pending-rebuild flag in the message for diagnosis.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        previous: Scene | None = None
        while True:
            await asyncio.sleep(0)
            current = self.app.current_tree
            pending = self._rebuild_pending()
            if not pending and previous is not None and current == previous:
                return
            previous = current
            if loop.time() >= deadline:
                raise TimeoutError(
                    f"tree did not settle within {timeout:.2f}s "
                    f"(rebuild pending: {pending}). The handler may schedule "
                    "work that never completes, or an animation never stops."
                )

    def patches(self) -> list[Patch]:
        """Return every patch applied since mount, in application order.

        Returns:
            The flattened list of applied patches (newest last).
        """
        return list(self._patches)

    def node_at(self, path: Path) -> Node:
        """Resolve a node by its IR path in the current scene.

        Args:
            path: The node address (see :data:`tempestroid.core.ir.Path`).

        Returns:
            The node at ``path``.

        Raises:
            KeyError: If the path does not resolve.
        """
        return node_at(self.scene(), path)

    def _record_patches(self, patches: list[Patch]) -> None:
        """Record a patch batch applied by the app's rebuild loop.

        Args:
            patches: The patch batch the app produced for one rebuild.
        """
        self._patches.extend(patches)

    def _rebuild_pending(self) -> bool:
        """Whether the app has a coalesced rebuild scheduled but not yet run.

        Reads the app's internal ``_rebuild_scheduled`` flag, the authoritative
        signal that ``request_rebuild`` queued a ``_rebuild`` that has not fired.

        Returns:
            ``True`` while a rebuild is pending.
        """
        # The flag is the app's own settle signal; the test driver is the one
        # consumer outside the loop that legitimately reads it.
        return bool(self.app._rebuild_scheduled)  # pyright: ignore[reportPrivateUsage]
