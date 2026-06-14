"""Pure helpers for walking and inspecting a built :class:`Scene`/:class:`Node`.

The test driver never touches a renderer. It queries the **built IR** — the same
normalized :class:`~tempestroid.core.ir.Node` tree the reconciler diffs and the
two leaf renderers (Qt, Compose) realize — so a locator/assertion resolves
against renderer-agnostic data and the same script runs on every backend.

A node is addressed by a **path**, exactly as the reconciler addresses one (see
:data:`tempestroid.core.ir.Path`): a tuple of child indices from the root, with
the reserved leading ``"overlay"`` token addressing the :class:`Scene` overlay
layer. ``()`` is the root, ``(0, 2)`` the third child of the first child, and
``("overlay", 0, 1)`` the second child of the first overlay.
"""

from __future__ import annotations

from collections.abc import Iterator

from tempest_core.core.ir import Node, Path, Scene

__all__ = [
    "walk_scene",
    "walk_node",
    "node_at",
    "visible_text",
    "read_prop",
    "node_role",
    "node_label",
]

#: Prop keys that carry a node's user-visible text, in priority order. ``Text``
#: stores its string under ``content``, ``Button`` under ``label``, and text
#: inputs under ``value`` (with a fallback ``placeholder`` for the empty state).
_TEXT_PROP_KEYS: tuple[str, ...] = ("content", "label", "value", "title", "text")


def walk_scene(scene: Scene) -> Iterator[tuple[Path, Node]]:
    """Yield every ``(path, node)`` in a scene: the root tree then each overlay.

    The root tree is walked depth-first with integer paths; each overlay ``i`` is
    then walked under the reserved ``("overlay", i, ...)`` prefix, mirroring how
    the reconciler addresses the overlay layer.

    Args:
        scene: The built scene to walk.

    Yields:
        ``(path, node)`` pairs in document order (root subtree first, then
        overlays in ascending z-order).
    """
    yield from walk_node(scene.root, ())
    for index, overlay in enumerate(scene.overlays):
        yield from walk_node(overlay, ("overlay", index))


def walk_node(node: Node, prefix: Path = ()) -> Iterator[tuple[Path, Node]]:
    """Yield ``(path, node)`` for ``node`` and every descendant, depth-first.

    Args:
        node: The subtree root to walk.
        prefix: The path of ``node`` itself (``()`` when it is the scene root).

    Yields:
        ``(path, node)`` pairs, the subtree root first then its descendants.
    """
    yield prefix, node
    for index, child in enumerate(node.children):
        yield from walk_node(child, (*prefix, index))


def node_at(scene: Scene, path: Path) -> Node:
    """Resolve the node addressed by ``path`` within ``scene``.

    Args:
        scene: The scene to index into.
        path: The node address (see the module docstring).

    Returns:
        The node at ``path``.

    Raises:
        KeyError: If the path does not resolve to a node in the scene.
    """
    steps = list(path)
    if steps and steps[0] == "overlay":
        if len(steps) < 2 or not isinstance(steps[1], int):
            raise KeyError(f"malformed overlay path: {path!r}")
        overlay_index = steps[1]
        if not 0 <= overlay_index < len(scene.overlays):
            raise KeyError(f"no overlay at index {overlay_index} (path {path!r})")
        node = scene.overlays[overlay_index]
        rest = steps[2:]
    else:
        node = scene.root
        rest = steps
    for step in rest:
        if not isinstance(step, int):
            raise KeyError(f"malformed child step {step!r} in path {path!r}")
        if not 0 <= step < len(node.children):
            raise KeyError(f"no child at index {step} in path {path!r}")
        node = node.children[step]
    return node


def read_prop(node: Node, name: str, default: object = None) -> object:
    """Read a single prop off a node, returning ``default`` when absent.

    Args:
        node: The node to read from.
        name: The prop name.
        default: The value to return when the prop is missing.

    Returns:
        The prop value, or ``default``.
    """
    return node.props.get(name, default)


def visible_text(node: Node) -> str:
    """Extract the user-visible text of a subtree, descendants joined by spaces.

    Collects the text-carrying prop (``content``/``label``/``value``/…) of the
    node and every descendant, in document order, so a locator can match text
    that a container composes from several leaves (e.g. a row of labels). Empty
    strings are skipped, so a blank input contributes nothing.

    Args:
        node: The subtree root.

    Returns:
        The concatenated visible text (``""`` when the subtree carries none).
    """
    parts: list[str] = []
    for _, descendant in walk_node(node):
        text = _own_text(descendant)
        if text:
            parts.append(text)
    return " ".join(parts)


def _own_text(node: Node) -> str:
    """Return a node's own text from its first present text prop.

    Args:
        node: The node to inspect.

    Returns:
        The node's own text, or ``""`` when it carries none.
    """
    for key in _TEXT_PROP_KEYS:
        value = node.props.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def node_role(node: Node) -> str | None:
    """Return a node's accessibility role, if any.

    The role comes from the node's :class:`~tempestroid.widgets.Semantics`
    (``semantics.role``); a node with no explicit semantics has no role.

    Args:
        node: The node to inspect.

    Returns:
        The role string, or ``None``.
    """
    semantics = node.props.get("semantics")
    role = getattr(semantics, "role", None)
    return role if isinstance(role, str) else None


def node_label(node: Node) -> str | None:
    """Return a node's accessibility label, if any.

    The label comes from the node's :class:`~tempestroid.widgets.Semantics`
    (``semantics.label``).

    Args:
        node: The node to inspect.

    Returns:
        The accessible label string, or ``None``.
    """
    semantics = node.props.get("semantics")
    label = getattr(semantics, "label", None)
    return label if isinstance(label, str) else None
