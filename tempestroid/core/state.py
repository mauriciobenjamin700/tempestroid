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
from typing import Generic, TypeVar, cast

from tempestroid.core.ir import Node, Patch
from tempestroid.core.reconciler import build, diff
from tempestroid.navigation import NavStack, Route
from tempestroid.widgets import LazyColumn, LazyGrid, LazyRow, SectionList, Widget

__all__ = ["App"]

S = TypeVar("S")

#: The virtualized list widgets whose visible window the app tracks and slides.
_LAZY_LISTS: tuple[type[Widget], ...] = (LazyColumn, LazyRow, LazyGrid)


class App(Generic[S]):
    """Owns app state and drives coalesced rebuilds.

    The ``view`` receives the app itself, so it can read ``app.state`` and wire
    handlers that call :meth:`set_state` (sync or from inside an ``async``
    handler). This avoids any circular dependency between the view and the app.

    The app also owns a :class:`~tempestroid.navigation.NavStack` (``self.nav``),
    independent of the generic state ``S``. The ``view`` reads ``app.nav.top`` to
    decide which screen to build; :meth:`push`/:meth:`pop`/:meth:`replace`/
    :meth:`reset` mutate the stack and schedule the same coalesced rebuild as a
    state change, so navigation flows through the existing diff with no new patch
    kind.

    Type Args:
        S: The application state type.
    """

    def __init__(
        self,
        state: S,
        view: Callable[[App[S]], Widget],
        apply_patches: Callable[[list[Patch]], None],
        nav: NavStack | None = None,
    ) -> None:
        """Initialize the app.

        Args:
            state: The initial application state.
            view: Builds the widget tree from the app (reads ``app.state`` and
                ``app.nav.top``).
            apply_patches: Renderer callback that applies a patch list.
            nav: The initial navigation stack. Defaults to a fresh
                :class:`~tempestroid.navigation.NavStack` with the root route.
        """
        self.state: S = state
        self.nav: NavStack = nav if nav is not None else NavStack()
        self._view: Callable[[App[S]], Widget] = view
        self._apply: Callable[[list[Patch]], None] = apply_patches
        self._current: Node | None = None
        self._rebuild_scheduled: bool = False
        # Visible-window overrides for virtualized lists, keyed by the list's
        # `key`; SectionList sections are keyed `"<list_key>::<section_title>"`.
        # Injected into the freshly built tree (see `_build`) so a slid window
        # survives the view re-running, and the materialized window children
        # cross to the renderer as the list node's `children`.
        self._windows: dict[str, tuple[int, int]] = {}

    def start(self) -> Node:
        """Build the initial IR tree and record it as the current tree.

        Returns:
            The root IR node, ready to hand to a renderer's ``mount``.
        """
        self._current = self._build()
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
        new = build(self._inject_windows(view(self)))
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

    def slide_window(self, key: str, start: int, end: int) -> None:
        """Set the visible window of a virtualized list and request a rebuild.

        A renderer (or the device bridge) calls this from a list's scroll handler:
        the new ``[start, end)`` window is recorded by the list's ``key`` and
        injected into the next build, so :class:`LazyColumn`/:class:`LazyRow`/
        :class:`LazyGrid` materialize the slid window. Through the keyed diff this
        becomes a minimal remove/reorder/insert patch sequence.

        Args:
            key: The ``key`` of the target list widget.
            start: The first visible index (inclusive).
            end: The one-past-last visible index (exclusive).
        """
        self._windows[key] = (start, end)
        self.request_rebuild()

    def slide_section_window(
        self, key: str, section_title: str, start: int, end: int
    ) -> None:
        """Set the visible window of one section of a :class:`SectionList`.

        Args:
            key: The ``key`` of the target :class:`SectionList` widget.
            section_title: The ``title`` of the section to slide.
            start: The first visible index (inclusive) within that section.
            end: The one-past-last visible index (exclusive) within that section.
        """
        self._windows[f"{key}::{section_title}"] = (start, end)
        self.request_rebuild()

    def _build(self) -> Node:
        """Build the current view, injecting any tracked list windows first.

        Returns:
            The freshly built IR node tree with virtualized lists materialized at
            their tracked windows.
        """
        return build(self._inject_windows(self._view(self)))

    def _inject_windows(self, widget: Widget) -> Widget:
        """Rewrite a widget tree to carry the app's tracked list windows.

        Walks the tree by ``child_field_names``; a virtualized list with a tracked
        window (matched by ``key``) is copied with its ``window`` set, so its
        ``child_nodes`` materializes the slid window at build time. Trees without
        any tracked window are returned untouched (the common, allocation-free
        path), so lists fall back to their declared initial window on first mount.

        Args:
            widget: The root widget built by the view.

        Returns:
            The (possibly rewritten) widget tree.
        """
        if not self._windows:
            return widget
        return self._inject(widget)

    def _inject(self, widget: Widget) -> Widget:
        """Recursively apply tracked windows to a widget and its children.

        Args:
            widget: The widget to rewrite.

        Returns:
            The rewritten widget (a copy when a window applies or a child changed).
        """
        updates: dict[str, object] = {}

        if isinstance(widget, _LAZY_LISTS) and widget.key in self._windows:
            updates["window"] = self._windows[widget.key]
        elif isinstance(widget, SectionList):
            sections = [
                section.model_copy(update={"window": window})
                if (
                    widget.key is not None
                    and (
                        window := self._windows.get(
                            f"{widget.key}::{section.title}"
                        )
                    )
                    is not None
                )
                else section
                for section in widget.sections
            ]
            if any(
                new is not old
                for new, old in zip(sections, widget.sections, strict=True)
            ):
                updates["sections"] = sections

        for field in type(widget).child_field_names:
            value = getattr(widget, field)
            if isinstance(value, list):
                children = cast("list[Widget]", value)
                new_children = [self._inject(child) for child in children]
                if any(
                    new is not old
                    for new, old in zip(new_children, children, strict=True)
                ):
                    updates[field] = new_children
            elif isinstance(value, Widget):
                new_child = self._inject(value)
                if new_child is not value:
                    updates[field] = new_child

        return widget.model_copy(update=updates) if updates else widget

    def push(self, route: Route) -> None:
        """Push a route onto the navigation stack and request a rebuild.

        Args:
            route: The destination route to navigate to.
        """
        self.nav.stack.append(route)
        self.request_rebuild()

    def pop(self) -> bool:
        """Pop the top route, returning to the previous screen.

        At the root (a single route on the stack) this is a no-op: the stack is
        left untouched so the host can take its default back action (e.g. close
        the app on Android).

        Returns:
            ``True`` if a route was popped, ``False`` if already at the root.
        """
        if not self.nav.can_pop:
            return False
        self.nav.stack.pop()
        self.request_rebuild()
        return True

    def replace(self, route: Route) -> None:
        """Replace the top route in place (no stack-depth change).

        Args:
            route: The route to put on top, replacing the current screen.
        """
        self.nav.stack[-1] = route
        self.request_rebuild()

    def reset(self, stack: list[Route]) -> None:
        """Replace the entire navigation stack and request a rebuild.

        Args:
            stack: The new, non-empty route stack (e.g. for a deep link).

        Raises:
            ValueError: If ``stack`` is empty — an app must always have a screen.
        """
        if not stack:
            raise ValueError("navigation stack cannot be empty")
        self.nav.stack = list(stack)
        self.request_rebuild()

    def request_rebuild(self) -> None:
        """Schedule a single rebuild on the event loop.

        Repeated calls before the loop next runs are coalesced into one rebuild.
        """
        if self._rebuild_scheduled:
            return
        self._rebuild_scheduled = True
        self._loop().call_soon(self._rebuild)

    def _rebuild(self) -> None:
        """Rebuild the tree, diff against the current one, and apply patches."""
        self._rebuild_scheduled = False
        if self._current is None:
            return
        new = self._build()
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
