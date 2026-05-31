"""Application state and the coalesced rebuild loop.

An :class:`App` ties together mutable state, a ``view`` function that turns that
state into a widget tree, and a renderer's ``apply`` callback. State mutations
schedule a rebuild on the asyncio loop; several mutations in the same tick
collapse into a single ``build → diff → patch`` pass, so the UI never flickers
or does redundant work.

The runtime is renderer-agnostic — it only emits patches and hands them to the
``apply_patches`` callback. The Qt runner wires this to :class:`QtRenderer`; a
future Compose runner would wire the same loop to the device.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Generic, TypeVar

from tempestroid.core.ir import Node, Patch
from tempestroid.core.reconciler import build, diff
from tempestroid.widgets import Widget

__all__ = ["App"]

S = TypeVar("S")


class App(Generic[S]):
    """Owns app state and drives coalesced rebuilds.

    The ``view`` receives the app itself, so it can read ``app.state`` and wire
    handlers that call :meth:`set_state` (sync or from inside an ``async``
    handler). This avoids any circular dependency between the view and the app.

    Type Args:
        S: The application state type.
    """

    def __init__(
        self,
        state: S,
        view: Callable[[App[S]], Widget],
        apply_patches: Callable[[list[Patch]], None],
    ) -> None:
        """Initialize the app.

        Args:
            state: The initial application state.
            view: Builds the widget tree from the app (reads ``app.state``).
            apply_patches: Renderer callback that applies a patch list.
        """
        self.state: S = state
        self._view: Callable[[App[S]], Widget] = view
        self._apply: Callable[[list[Patch]], None] = apply_patches
        self._current: Node | None = None
        self._rebuild_scheduled: bool = False

    def start(self) -> Node:
        """Build the initial IR tree and record it as the current tree.

        Returns:
            The root IR node, ready to hand to a renderer's ``mount``.
        """
        self._current = build(self._view(self))
        return self._current

    @property
    def current_tree(self) -> Node | None:
        """The most recently built IR tree (``None`` before :meth:`start`).

        Returns:
            The current root node, or ``None``.
        """
        return self._current

    def swap_view(self, view: Callable[[App[S]], Widget]) -> list[Patch]:
        """Swap the ``view`` function and rebuild against the live state.

        This is **stateful hot reload**: unlike a hot restart (which throws the
        state away and remounts), it keeps the current state object and diffs the
        tree built by the *new* view against the current tree, so on-screen state
        survives a code edit. The new tree is built eagerly (synchronously) so an
        incompatible view — e.g. one reading a state attribute the preserved
        state lacks — raises here and the old view stays installed, letting the
        caller fall back to a clean restart.

        Args:
            view: The new view function (typically from a reloaded module).

        Returns:
            The patches applied to reconcile the new tree (``[]`` if unchanged).

        Raises:
            RuntimeError: If called before :meth:`start`.
            Exception: Whatever the new ``view``/``build`` raises — the swap is
                rolled back (the old view stays installed) before re-raising.
        """
        if self._current is None:
            raise RuntimeError("cannot swap_view before start()")
        # Build with the new view eagerly so a failure aborts before we commit;
        # the old self._view is untouched until the build succeeds.
        new = build(view(self))
        self._view = view
        patches = diff(self._current, new)
        self._current = new
        if patches:
            self._apply(patches)
        return patches

    def set_state(self, mutate: Callable[[S], None] | None = None) -> None:
        """Mutate state (optionally) and request a coalesced rebuild.

        Args:
            mutate: Optional callback that mutates ``self.state`` in place.
        """
        if mutate is not None:
            mutate(self.state)
        self.request_rebuild()

    def request_rebuild(self) -> None:
        """Schedule a single rebuild on the event loop.

        Repeated calls before the loop next runs are coalesced into one rebuild.
        """
        if self._rebuild_scheduled:
            return
        self._rebuild_scheduled = True
        # If scheduling fails (e.g. a closed loop), clear the flag so a later
        # call can retry — otherwise the app would be wedged with no rebuilds.
        try:
            self._loop().call_soon(self._rebuild)
        except RuntimeError:
            self._rebuild_scheduled = False
            raise

    def _rebuild(self) -> None:
        """Rebuild the tree, diff against the current one, and apply patches."""
        self._rebuild_scheduled = False
        if self._current is None:
            return
        new = build(self._view(self))
        patches = diff(self._current, new)
        self._current = new
        if patches:
            self._apply(patches)

    @staticmethod
    def _loop() -> asyncio.AbstractEventLoop:
        """Return the loop to schedule on (running loop, else the policy loop).

        Returns:
            The asyncio event loop.
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()
