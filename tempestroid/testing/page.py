"""The :class:`Page` — the driver's top-level, renderer-agnostic surface.

A page binds a :class:`~tempestroid.testing.backend.TestBackend` and gives a test
everything it needs: semantic locator constructors (``get_by_*``), user actions
(:meth:`tap`, :meth:`fill`), and auto-waiting assertions (``expect_*``). It is
the headless analogue of a Playwright ``Page``. Crucially, nothing here is
renderer-specific — the page only ever speaks the IR + typed-event vocabulary the
backend exposes — so a script written against a :class:`Page` runs unchanged on
every backend (headless now; Qt/emulator/device once Trilho F8 lands them).

Every assertion **auto-waits**: it re-resolves its locator against the live scene
and settles the tree, polling until the condition holds or a timeout elapses —
there are no fixed sleeps, so timing flake cannot creep in.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tempest_core.core.ir import Node

from tempestroid.testing.backend import TestBackend
from tempestroid.testing.locator import (
    Locator,
    by_key,
    by_prop,
    by_role,
    by_semantics,
    by_text,
)
from tempestroid.testing.tree import visible_text, walk_scene

__all__ = ["Page"]

#: Default per-assertion timeout, in seconds. An assertion ends the instant its
#: condition holds; this only bounds the wait for a condition that never does.
_DEFAULT_EXPECT_TIMEOUT = 5.0


class Page:
    """Drive a mounted app: locate nodes, act on them, assert with auto-wait.

    Construct a page over any :class:`~tempestroid.testing.backend.TestBackend`
    and :meth:`mount` it (the runner does this for you). Then query with
    ``get_by_*``, act with :meth:`tap`/:meth:`fill`, and assert with
    ``expect_*``.

    Methods:
        mount: Mount the underlying backend (build + start the app).
        get_by_key: Locate a node by its stable IR ``key``.
        get_by_text: Locate a node by its visible text.
        get_by_role: Locate a node by accessibility role (and optional name).
        get_by_semantics: Locate a node by accessibility label/role.
        get_by_prop: Locate a node by an exact prop value.
        tap: Inject a tap on a located node.
        fill: Inject a text-change on a located input node.
        back: Pop the navigation stack (a system back press).
        expect_text: Auto-wait until some node's visible text contains a string.
        expect_visible: Auto-wait until a locator matches at least one node.
        expect_count: Auto-wait until a locator matches exactly ``n`` nodes.
        snapshot: Return a JSON-able dump of the current scene (a "screenshot").
    """

    def __init__(self, backend: TestBackend) -> None:
        """Initialize the page over a backend.

        Args:
            backend: The target backend to automate.
        """
        self._backend = backend

    @property
    def backend(self) -> TestBackend:
        """The bound backend.

        Returns:
            The :class:`~tempestroid.testing.backend.TestBackend`.
        """
        return self._backend

    async def mount(self) -> None:
        """Mount the underlying backend (build + start the app)."""
        await self._backend.mount()

    # -- Locators -----------------------------------------------------------

    def get_by_key(self, key: str) -> Locator:
        """Locate a node by its stable IR ``key``.

        Args:
            key: The exact node key to match.

        Returns:
            A lazy locator resolved against the live scene.
        """
        return by_key(self, key)

    def get_by_text(self, substring: str, *, exact: bool = False) -> Locator:
        """Locate a node by its visible text.

        Args:
            substring: The text to look for.
            exact: Require the whole visible text to equal ``substring`` when
                ``True``; otherwise a substring match.

        Returns:
            A lazy locator resolved against the live scene.
        """
        return by_text(self, substring, exact=exact)

    def get_by_role(self, role: str, *, name: str | None = None) -> Locator:
        """Locate a node by its accessibility role (and optional name).

        Args:
            role: The accessibility role (``semantics.role``).
            name: Optional accessible name to also require (``semantics.label``).

        Returns:
            A lazy locator resolved against the live scene.
        """
        return by_role(self, role, name=name)

    def get_by_semantics(
        self, *, label: str | None = None, role: str | None = None
    ) -> Locator:
        """Locate a node by its accessibility semantics.

        Args:
            label: Optional accessible label to require.
            role: Optional accessibility role to require.

        Returns:
            A lazy locator resolved against the live scene.
        """
        return by_semantics(self, label=label, role=role)

    def get_by_prop(self, name: str, value: object) -> Locator:
        """Locate a node by an exact prop value.

        Args:
            name: The prop name to compare.
            value: The value the prop must equal.

        Returns:
            A lazy locator resolved against the live scene.
        """
        return by_prop(self, name, value)

    # -- Actions ------------------------------------------------------------

    async def tap(self, locator: Locator, **payload: object) -> None:
        """Inject a tap on the node a locator uniquely resolves to.

        Resolves the locator against the live scene, picks the node's tap-style
        handler (``on_click`` for a button, ``on_tap`` for a gesture detector),
        and dispatches a :class:`~tempestroid.widgets.events.TapEvent`; the
        backend auto-waits for the resulting rebuild to settle.

        Args:
            locator: A locator resolving to exactly one node.
            **payload: Extra event payload fields (e.g. ``x``/``y``).

        Raises:
            LocatorError: If the locator matches zero or many nodes.
            KeyError: If the node carries no tap handler.
        """
        _, node = locator.resolve()
        handler_name = _tap_handler_name(node)
        await self._backend.dispatch(node, handler_name, dict(payload))

    async def fill(self, locator: Locator, text: str, **payload: object) -> None:
        """Inject a text-change on the input node a locator resolves to.

        Resolves the locator, picks its change handler (``on_change``), and
        dispatches a :class:`~tempestroid.widgets.events.TextChangeEvent` with
        ``value=text``; the backend auto-waits to settle.

        Args:
            locator: A locator resolving to exactly one input node.
            text: The new text value.
            **payload: Extra event payload fields (e.g. ``valid``).

        Raises:
            LocatorError: If the locator matches zero or many nodes.
            KeyError: If the node carries no change handler.
        """
        _, node = locator.resolve()
        handler_name = _change_handler_name(node)
        await self._backend.dispatch(node, handler_name, {"value": text, **payload})

    async def back(self) -> None:
        """Pop the navigation stack (the headless analogue of a system back press).

        Only a backend that exposes the underlying app (the headless one) supports
        this directly; other backends will fire their platform back action. Settles
        the tree afterwards.

        Raises:
            NotImplementedError: If the backend does not expose an app to pop.
        """
        app = getattr(self._backend, "app", None)
        if app is None or not hasattr(app, "pop"):
            raise NotImplementedError(
                "this backend does not support back(); it will arrive with the "
                "Qt/device backends (F8)"
            )
        app.pop()
        await self._backend.settle()

    # -- Assertions (auto-waiting) -----------------------------------------

    async def expect_text(
        self, substring: str, *, timeout: float = _DEFAULT_EXPECT_TIMEOUT
    ) -> None:
        """Auto-wait until the scene's visible text contains ``substring``.

        Polls — settling the tree and re-scanning the whole scene each round —
        until some node's visible text contains ``substring`` or ``timeout``
        elapses.

        Args:
            substring: The text expected to appear somewhere in the UI.
            timeout: Maximum seconds to wait.

        Raises:
            AssertionError: If the text never appears, with the current scene
                dumped for diagnosis.
        """
        await self._wait_for(
            lambda: any(
                substring in visible_text(node)
                for _, node in walk_scene(self._backend.scene())
            ),
            f"expected text {substring!r} to be visible",
            timeout,
        )

    async def expect_visible(
        self, locator: Locator, *, timeout: float = _DEFAULT_EXPECT_TIMEOUT
    ) -> None:
        """Auto-wait until ``locator`` matches at least one node.

        Args:
            locator: The locator expected to find a node.
            timeout: Maximum seconds to wait.

        Raises:
            AssertionError: If the locator never matches, with the scene dumped.
        """
        await self._wait_for(
            lambda: locator.count() >= 1,
            f"expected {locator.description} to be visible",
            timeout,
        )

    async def expect_count(
        self, locator: Locator, n: int, *, timeout: float = _DEFAULT_EXPECT_TIMEOUT
    ) -> None:
        """Auto-wait until ``locator`` matches exactly ``n`` nodes.

        Args:
            locator: The locator to count.
            n: The expected number of matches.
            timeout: Maximum seconds to wait.

        Raises:
            AssertionError: If the count never reaches ``n``, with the scene
                dumped.
        """
        await self._wait_for(
            lambda: locator.count() == n,
            f"expected {locator.description} to match {n} node(s)",
            timeout,
        )

    # -- Snapshot -----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-able dump of the current scene — a "screenshot" of the IR.

        This is the headless analogue of a pixel screenshot: a stable, diffable
        serialization of the built tree (types, keys, the JSON-primitive props,
        children) suitable for golden comparison. Handlers and non-serializable
        prop values are dropped, so the dump is deterministic. A real pixel
        screenshot is a renderer concern and arrives with the Qt/device backends
        (Trilho F8).

        Returns:
            A nested ``{"root": ..., "overlays": [...]}`` dict.
        """
        scene = self._backend.scene()
        return {
            "root": _dump_node(scene.root),
            "overlays": [_dump_node(o) for o in scene.overlays],
        }

    async def _wait_for(
        self, condition: Callable[[], bool], message: str, timeout: float
    ) -> None:
        """Poll a condition with auto-wait until it holds or ``timeout`` elapses.

        Settles the tree, evaluates ``condition`` (a zero-arg predicate), and
        repeats — yielding to the loop, never sleeping a fixed time — until the
        condition is true or the deadline passes.

        Args:
            condition: A zero-argument callable returning ``True`` when the
                assertion is satisfied.
            message: The assertion message used on timeout.
            timeout: Maximum seconds to wait.

        Raises:
            AssertionError: If ``condition`` never holds within ``timeout``.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            # Settle only for the time left until the deadline, so a tree that
            # never stabilizes (e.g. a running animation) can't stretch the total
            # wait past ``timeout``.
            remaining = deadline - loop.time()
            try:
                await self._backend.settle(timeout=max(0.0, remaining))
            except TimeoutError:
                pass
            if condition():
                return
            if loop.time() >= deadline:
                dump = self.snapshot()
                raise AssertionError(f"{message}\ncurrent tree:\n{dump}")
            await asyncio.sleep(0)


def _tap_handler_name(node: Node) -> str:
    """Pick a node's tap-style handler prop name.

    Args:
        node: The node to inspect.

    Returns:
        The first present tap handler name (``on_click`` then ``on_tap``),
        defaulting to ``"on_click"``.
    """
    for name in ("on_click", "on_tap"):
        if callable(node.props.get(name)):
            return name
    return "on_click"


def _change_handler_name(node: Node) -> str:
    """Pick a node's change handler prop name.

    Args:
        node: The node to inspect.

    Returns:
        The change handler name (always ``"on_change"`` today).
    """
    return "on_change"


def _dump_node(node: Node) -> dict[str, Any]:
    """Serialize a node to a JSON-able dict, dropping non-serializable props.

    Keeps the type, key, the JSON-primitive-valued props, and recursively the
    children, so the dump is stable and comparable as a golden.

    Args:
        node: The node to serialize.

    Returns:
        A JSON-able node dump.
    """
    props: dict[str, Any] = {
        name: value
        for name, value in node.props.items()
        if isinstance(value, (str, int, float, bool))
    }
    return {
        "type": node.type,
        "key": node.key,
        "props": props,
        "children": [_dump_node(c) for c in node.children],
    }
