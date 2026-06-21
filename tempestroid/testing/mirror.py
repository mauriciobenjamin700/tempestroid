"""Host-side mirror of the device's live serialized scene.

The emulator/device backend never holds the live :class:`~tempest_core.core.ir.Node`
objects — those live in the interpreter on the device. Instead the device's
code-push client POSTs the **serialized** mount JSON (and every patch batch) back
over the dev server, and this module reconstructs a host-side :class:`Scene` from
that JSON and keeps it in step by applying each patch batch.

The reconstruction is the exact inverse of
:func:`tempestroid.bridge.serializer.serialize_node` /
:func:`~tempestroid.bridge.serializer.serialize_patch`:

* :func:`deserialize_scene` turns a :class:`~tempestroid.bridge.protocol.MountMessage`
  dump (``root`` + ``overlays``) into a :class:`Scene`. Handler props arrive as
  ``{"$handler": token, "event": EventName}`` and are **kept verbatim** (the
  token is how the backend addresses a tap back to the device — the callable
  never crosses), so the mirror's nodes carry the token string where the headless
  backend's nodes carry the real callable. Both satisfy the same test protocol.
* :func:`apply_patches` replays serialized patch batches
  (``replace``/``update``/``insert``/``remove``/``reorder``) onto the mirror by
  path, mirroring what the Kotlin ``TempestTree`` does on the device — host-side,
  in pure Python, so the mirror provably tracks the engine's own output (the
  round-trip is unit-tested against ``serialize_node``/``serialize_patch``).

The mirror is the source of truth the :class:`~tempestroid.testing.EmulatorBackend`
returns from ``scene()``, so the Page/Locator/expect_* layer is unchanged.
"""

from __future__ import annotations

from typing import Any

from tempest_core.core.ir import Node, Path, Scene

__all__ = ["deserialize_node", "deserialize_scene", "apply_patches"]

#: The reserved path step that addresses the scene overlay layer (mirrors
#: :data:`tempest_core.core.ir.Path`'s leading ``"overlay"`` token).
_OVERLAY_STEP = "overlay"


def deserialize_node(data: dict[str, Any]) -> Node:
    """Reconstruct an IR node (and its subtree) from serialized JSON.

    The inverse of :func:`tempestroid.bridge.serializer.serialize_node`: builds a
    :class:`~tempest_core.core.ir.Node` from ``{"type", "key", "props",
    "children"}``. Props are copied verbatim — handler refs (``{"$handler":
    ...}``) and the Compose ``style`` spec are kept as the dicts they arrived as,
    since the host mirror only needs to address them, never to render them.

    Args:
        data: A serialized node dict (as produced on the device).

    Returns:
        The reconstructed :class:`Node`.
    """
    return Node(
        type=data["type"],
        key=data.get("key"),
        props=dict(data.get("props", {})),
        children=[deserialize_node(child) for child in data.get("children", [])],
    )


def deserialize_scene(mount: dict[str, Any]) -> Scene:
    """Reconstruct a :class:`Scene` from a serialized mount message.

    Args:
        mount: A :class:`~tempestroid.bridge.protocol.MountMessage` dump, carrying
            ``root`` (a serialized node) and ``overlays`` (a list of serialized
            nodes).

    Returns:
        The reconstructed :class:`Scene` (root tree + overlay layer).
    """
    return Scene(
        root=deserialize_node(mount["root"]),
        overlays=[deserialize_node(node) for node in mount.get("overlays", [])],
    )


def apply_patches(scene: Scene, patches: list[dict[str, Any]]) -> Scene:
    """Apply a batch of serialized patches to the mirror, returning a new scene.

    Replays each serialized patch (the output of
    :func:`tempestroid.bridge.serializer.serialize_patch`) onto a mutable copy of
    ``scene`` by path. The host-side analogue of the Kotlin ``TempestTree`` patch
    application; the patch ``op`` and shape match the serializer exactly:

    * ``replace`` → swap the subtree at ``path`` for ``node``.
    * ``update``  → set ``set`` props and drop ``unset`` props on the node.
    * ``insert``  → insert ``node`` as child ``index`` under ``path``.
    * ``remove``  → drop child ``index`` under ``path``.
    * ``reorder`` → permute children under ``path`` by ``order``.

    Args:
        scene: The current mirror scene.
        patches: The serialized patch batch to apply, in order.

    Returns:
        A new :class:`Scene` with every patch applied.

    Raises:
        KeyError: If a patch addresses a path that does not resolve.
        ValueError: If a patch carries an unknown ``op``.
    """
    root = scene.root.model_copy(deep=True)
    overlays = [overlay.model_copy(deep=True) for overlay in scene.overlays]
    for patch in patches:
        root, overlays = _apply_one(root, overlays, patch)
    return Scene(root=root, overlays=overlays)


def _apply_one(
    root: Node,
    overlays: list[Node],
    patch: dict[str, Any],
) -> tuple[Node, list[Node]]:
    """Apply one serialized patch to the (root, overlays) pair.

    The overlay layer is addressed by a leading ``"overlay"`` path step, mirroring
    :func:`tempestroid.core.reconciler` / ``diff_scene``: a bare ``("overlay",)``
    path is a layer-level insert/remove/reorder, ``("overlay", i, ...)`` targets
    overlay ``i``'s subtree.

    Args:
        root: The current root node.
        overlays: The current overlay nodes.
        patch: One serialized patch dict.

    Returns:
        The updated ``(root, overlays)`` pair.

    Raises:
        ValueError: If the patch carries an unknown ``op``.
        KeyError: If the patch path does not resolve.
    """
    op: str = patch["op"]
    path: Path = tuple(patch["path"])
    if path and path[0] == _OVERLAY_STEP:
        new_overlays = _apply_to_overlays(overlays, op, path, patch)
        return root, new_overlays
    new_root = _apply_to_tree(root, op, path, patch)
    return new_root, overlays


def _apply_to_overlays(
    overlays: list[Node],
    op: str,
    path: Path,
    patch: dict[str, Any],
) -> list[Node]:
    """Apply a patch addressed at the overlay layer.

    Args:
        overlays: The current overlay nodes.
        op: The patch op.
        path: The patch path (begins with ``"overlay"``).
        patch: The full serialized patch.

    Returns:
        The updated overlay list.

    Raises:
        ValueError: If a layer-level patch carries an unexpected op.
        KeyError: If the patch path does not resolve.
    """
    if len(path) == 1:
        # Layer-level structural patch: the overlay list is the "children".
        return _structural(overlays, op, patch)
    # ("overlay", i, ...) — re-base onto overlay i's subtree.
    index = int(path[1])
    if index < 0 or index >= len(overlays):
        raise KeyError(f"overlay index {index} out of range (have {len(overlays)})")
    rebased = dict(patch)
    rebased["path"] = list(path[2:])
    new_overlays = list(overlays)
    new_overlays[index] = _apply_to_tree(overlays[index], op, tuple(path[2:]), rebased)
    return new_overlays


def _apply_to_tree(node: Node, op: str, path: Path, patch: dict[str, Any]) -> Node:
    """Apply a patch to the root tree (or a re-based overlay subtree).

    A ``replace`` or ``update`` targets the node *at* ``path``; an
    ``insert``/``remove``/``reorder`` targets the *children of* the node at
    ``path``. The walk is recursive so the patch lands deep in the tree.

    Args:
        node: The current (sub)tree root.
        op: The patch op.
        path: The path relative to ``node``.
        patch: The full serialized patch.

    Returns:
        The updated (sub)tree.

    Raises:
        ValueError: If the op is unknown.
        KeyError: If the path does not resolve to a child.
    """
    if op in ("replace", "update"):
        return _mutate_node(node, op, path, patch)
    # Structural ops act on the children of the node at `path`.
    return _mutate_children(node, path, op, patch)


def _mutate_node(node: Node, op: str, path: Path, patch: dict[str, Any]) -> Node:
    """Apply a node-targeting patch (``replace``/``update``) at ``path``.

    Args:
        node: The current (sub)tree root.
        op: ``"replace"`` or ``"update"``.
        path: The path to the target node, relative to ``node``.
        patch: The full serialized patch.

    Returns:
        The updated (sub)tree.

    Raises:
        KeyError: If the path does not resolve.
    """
    if not path:
        if op == "replace":
            return deserialize_node(patch["node"])
        return _update_props(node, patch.get("set", {}), patch.get("unset", []))
    index = int(path[0])
    children = list(node.children)
    if index < 0 or index >= len(children):
        raise KeyError(f"child index {index} out of range at {path}")
    children[index] = _mutate_node(children[index], op, path[1:], patch)
    return node.model_copy(update={"children": children})


def _mutate_children(node: Node, path: Path, op: str, patch: dict[str, Any]) -> Node:
    """Apply a structural patch (insert/remove/reorder) under ``path``.

    Args:
        node: The current (sub)tree root.
        path: The path to the *parent* whose children change.
        op: The structural op.
        patch: The full serialized patch.

    Returns:
        The updated (sub)tree.

    Raises:
        KeyError: If the path does not resolve.
        ValueError: If the op is unknown.
    """
    if not path:
        new_children = _structural(node.children, op, patch)
        return node.model_copy(update={"children": new_children})
    index = int(path[0])
    children = list(node.children)
    if index < 0 or index >= len(children):
        raise KeyError(f"child index {index} out of range at {path}")
    children[index] = _mutate_children(children[index], path[1:], op, patch)
    return node.model_copy(update={"children": children})


def _structural(children: list[Node], op: str, patch: dict[str, Any]) -> list[Node]:
    """Apply a structural op to a child list, returning a new list.

    Args:
        children: The current children (or overlay layer).
        op: ``"insert"``, ``"remove"``, or ``"reorder"``.
        patch: The full serialized patch.

    Returns:
        The new child list.

    Raises:
        ValueError: If ``op`` is not a structural op.
    """
    out = list(children)
    if op == "insert":
        out.insert(int(patch["index"]), deserialize_node(patch["node"]))
        return out
    if op == "remove":
        del out[int(patch["index"])]
        return out
    if op == "reorder":
        order: list[int] = [int(i) for i in patch["order"]]
        return [children[old_index] for old_index in order]
    raise ValueError(f"unknown structural patch op {op!r}")


def _update_props(
    node: Node, set_props: dict[str, Any], unset_props: list[str]
) -> Node:
    """Return a copy of ``node`` with props set/unset per an ``update`` patch.

    Args:
        node: The node to update.
        set_props: Props to add or overwrite.
        unset_props: Prop names to remove.

    Returns:
        The updated node copy.
    """
    props = dict(node.props)
    props.update(set_props)
    for name in unset_props:
        props.pop(name, None)
    return node.model_copy(update={"props": props})
