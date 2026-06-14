"""Lazy, semantic locators that resolve against the live IR.

A :class:`Locator` is a *query*, not a captured node. Like a Playwright locator,
it stores how to find a node — by key, by text, by accessibility role/label —
and re-runs that query against the **current** scene every time an action or
assertion needs it. Because the scene is rebuilt on every state change, this
"resolve late" rule is what makes the driver robust: a locator created before a
tap still points at the right node after the rebuild.

Locators are created through a :class:`~tempestroid.testing.Page` (``page.get_by_*``),
never constructed directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from tempest_core.core.ir import Node, Path

from tempestroid.testing.tree import (
    node_label,
    node_role,
    read_prop,
    visible_text,
    walk_scene,
)

if TYPE_CHECKING:
    from tempestroid.testing.page import Page

__all__ = ["Locator", "LocatorError"]


class LocatorError(Exception):
    """Raised when a locator resolves to zero or (when unique) many nodes."""


class Locator:
    """A lazy query for a node, resolved against the page's live scene.

    A locator never caches a node: :meth:`all` / :meth:`first` / :meth:`resolve`
    walk the *current* scene each call, so a locator survives rebuilds. Combine a
    locator's predicate with a human-readable description used in error messages.

    Methods:
        all: Return every matching ``(path, node)`` in document order.
        first: Return the first matching node (raises if none).
        resolve: Return the unique matching node (raises if zero or many).
        count: Return how many nodes currently match.
    """

    def __init__(
        self,
        page: Page,
        predicate: Callable[[Node], bool],
        description: str,
    ) -> None:
        """Initialize the locator.

        Args:
            page: The page whose live scene the locator queries.
            predicate: Returns ``True`` for a node that matches.
            description: A human-readable description for error messages
                (e.g. ``'get_by_key("inc")'``).
        """
        self._page = page
        self._predicate = predicate
        self._description = description

    @property
    def description(self) -> str:
        """The human-readable description of this query.

        Returns:
            The description string used in error messages.
        """
        return self._description

    def all(self) -> list[tuple[Path, Node]]:
        """Return every matching ``(path, node)`` in document order.

        Returns:
            The matches (empty list when none match).
        """
        scene = self._page.backend.scene()
        return [
            (path, node)
            for path, node in walk_scene(scene)
            if self._predicate(node)
        ]

    def count(self) -> int:
        """Return how many nodes currently match.

        Returns:
            The number of matching nodes.
        """
        return len(self.all())

    @property
    def first(self) -> Node:
        """Return the first matching node.

        Returns:
            The first match in document order.

        Raises:
            LocatorError: If no node matches.
        """
        matches = self.all()
        if not matches:
            raise LocatorError(f"no node matches {self._description}")
        _, node = matches[0]
        return node

    def resolve(self) -> tuple[Path, Node]:
        """Return the unique matching ``(path, node)``.

        Use this for actions that must target exactly one node (a tap, a fill).
        An ambiguous match is an error, not silently the first one, so a test
        fails loudly when its locator is not specific enough.

        Returns:
            The single matching ``(path, node)``.

        Raises:
            LocatorError: If zero or more than one node matches.
        """
        matches = self.all()
        if not matches:
            raise LocatorError(f"no node matches {self._description}")
        if len(matches) > 1:
            types = ", ".join(node.type for _, node in matches)
            raise LocatorError(
                f"{self._description} matched {len(matches)} nodes ({types}); "
                "refine the locator to target one"
            )
        return matches[0]


def by_key(page: Page, key: str) -> Locator:
    """Build a locator matching a node by its stable IR ``key``.

    Args:
        page: The page to bind to.
        key: The exact node key to match.

    Returns:
        The locator.
    """
    return Locator(page, lambda node: node.key == key, f"get_by_key({key!r})")


def by_text(page: Page, substring: str, *, exact: bool = False) -> Locator:
    """Build a locator matching a node by its visible text.

    Args:
        page: The page to bind to.
        substring: The text to look for in a node's visible text.
        exact: Match the whole visible text exactly when ``True``; otherwise a
            substring match.

    Returns:
        The locator.
    """

    def predicate(node: Node) -> bool:
        text = visible_text(node)
        return text == substring if exact else substring in text

    mode = "exact" if exact else "substring"
    return Locator(page, predicate, f"get_by_text({substring!r}, {mode})")


def by_role(page: Page, role: str, *, name: str | None = None) -> Locator:
    """Build a locator matching a node by its accessibility role (and label).

    Args:
        page: The page to bind to.
        role: The accessibility role to match (``semantics.role``).
        name: Optional accessible name to also require (``semantics.label``).

    Returns:
        The locator.
    """

    def predicate(node: Node) -> bool:
        if node_role(node) != role:
            return False
        return name is None or node_label(node) == name

    suffix = "" if name is None else f", name={name!r}"
    return Locator(page, predicate, f"get_by_role({role!r}{suffix})")


def by_semantics(
    page: Page, *, label: str | None = None, role: str | None = None
) -> Locator:
    """Build a locator matching a node by its accessibility semantics.

    At least one of ``label``/``role`` should be given; a node matches when every
    provided field equals the node's corresponding semantics field.

    Args:
        page: The page to bind to.
        label: Optional accessible label to require (``semantics.label``).
        role: Optional accessibility role to require (``semantics.role``).

    Returns:
        The locator.
    """

    def predicate(node: Node) -> bool:
        if label is not None and node_label(node) != label:
            return False
        return not (role is not None and node_role(node) != role)

    parts = [
        f"{field}={value!r}"
        for field, value in (("label", label), ("role", role))
        if value is not None
    ]
    joined = ", ".join(parts)
    return Locator(page, predicate, f"get_by_semantics({joined})")


def by_prop(page: Page, name: str, value: object) -> Locator:
    """Build a locator matching a node by an exact prop value.

    Args:
        page: The page to bind to.
        name: The prop name to compare.
        value: The value the prop must equal.

    Returns:
        The locator.
    """
    return Locator(
        page,
        lambda node: read_prop(node, name) == value,
        f"get_by_prop({name!r}, {value!r})",
    )
