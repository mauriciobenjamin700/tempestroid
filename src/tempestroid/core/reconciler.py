"""The reconciler: ``build`` widgets into IR nodes, then ``diff`` into patches.

This is the backbone of correctness and the *same* code on desktop and device —
only the leaf renderer that applies the patches differs. It is pure: data in,
patches out, no side effects and no renderer knowledge.

Diffing strategy (v1):

* Same position, same ``(type, key)`` → recurse, emitting an :class:`Update`
  for changed props.
* Differing ``type`` or ``key`` at a position → :class:`Replace` the subtree.
* Child lists are diffed **positionally** by default (:class:`Insert` /
  :class:`Remove` at the tail).
* When both child lists are fully keyed with the same unique key set and equal
  length, a pure permutation is detected and collapsed into a single
  :class:`Reorder` before recursing. Mixed insert+reorder falls back to the
  positional path — still correct, just less optimal. Keyed move-with-resize is
  a post-v1 refinement.
"""

from __future__ import annotations

from typing import Any

from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Remove,
    Reorder,
    Replace,
    Update,
)
from tempestroid.widgets import Widget

__all__ = ["build", "diff"]


def build(widget: Widget) -> Node:
    """Normalize a widget tree into an IR node tree.

    Children come from :meth:`Widget.child_nodes`; everything else on the widget
    (except ``key`` and the declared child slots) becomes a prop.

    Args:
        widget: The root widget to normalize.

    Returns:
        The root IR node.
    """
    children = [build(child) for child in widget.child_nodes()]
    skip = widget.child_field_names
    props: dict[str, Any] = {}
    for name in type(widget).model_fields:
        if name == "key" or name in skip:
            continue
        props[name] = getattr(widget, name)
    return Node(
        type=widget.widget_type,
        key=widget.key,
        props=props,
        children=children,
    )


def diff(old: Node, new: Node) -> list[Patch]:
    """Diff two IR node trees into an ordered list of patches.

    Patches are ordered so a renderer can apply them sequentially: a node's own
    update/reorder precedes its descendants' patches, and within a child list
    removals run tail-first before insertions.

    Args:
        old: The previously rendered tree.
        new: The freshly built tree.

    Returns:
        The patches that transform ``old`` into ``new`` (empty if identical).
    """
    patches: list[Patch] = []
    _reconcile(old, new, (), patches)
    return patches


def _reconcile(
    old: Node,
    new: Node,
    path: tuple[int, ...],
    patches: list[Patch],
) -> None:
    """Reconcile one node against another at ``path``, appending patches.

    Args:
        old: The old node at this position.
        new: The new node at this position.
        path: The address of this node.
        patches: The accumulator to append patches to.
    """
    if old.type != new.type or old.key != new.key:
        patches.append(Replace(path=path, node=new))
        return

    set_props, unset_props = _diff_props(old.props, new.props)
    if set_props or unset_props:
        patches.append(
            Update(path=path, set_props=set_props, unset_props=unset_props)
        )

    _reconcile_children(old.children, new.children, path, patches)


def _reconcile_children(
    old: list[Node],
    new: list[Node],
    path: tuple[int, ...],
    patches: list[Patch],
) -> None:
    """Reconcile two child lists under ``path``.

    Args:
        old: The old children.
        new: The new children.
        path: The address of the parent node.
        patches: The accumulator to append patches to.
    """
    if _is_pure_reorder(old, new):
        old_index_by_key = {node.key: index for index, node in enumerate(old)}
        order = [old_index_by_key[node.key] for node in new]
        if order != list(range(len(order))):
            patches.append(Reorder(path=path, order=order))
        for new_index, new_child in enumerate(new):
            _reconcile(
                old[order[new_index]], new_child, path + (new_index,), patches
            )
        return

    common = min(len(old), len(new))
    for index in range(common):
        _reconcile(old[index], new[index], path + (index,), patches)
    for index in range(len(old) - 1, common - 1, -1):
        patches.append(Remove(path=path, index=index))
    for index in range(common, len(new)):
        patches.append(Insert(path=path, index=index, node=new[index]))


def _is_pure_reorder(old: list[Node], new: list[Node]) -> bool:
    """Report whether two child lists differ only by a key permutation.

    Requires both lists to be non-empty, equal length, fully keyed with unique
    keys, and to share the same key set.

    Args:
        old: The old children.
        new: The new children.

    Returns:
        ``True`` when a single :class:`Reorder` can align the lists.
    """
    if not old or len(old) != len(new):
        return False
    old_keys = [node.key for node in old]
    new_keys = [node.key for node in new]
    if None in old_keys or None in new_keys:
        return False
    old_set = set(old_keys)
    if len(old_set) != len(old_keys) or len(set(new_keys)) != len(new_keys):
        return False
    return old_set == set(new_keys)


def _diff_props(
    old: dict[str, Any],
    new: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Compute the prop changes between two prop maps.

    Args:
        old: The old props.
        new: The new props.

    Returns:
        A ``(set_props, unset_props)`` pair: props to add/overwrite, and prop
        names that were removed.
    """
    set_props = {
        key: value
        for key, value in new.items()
        if key not in old or old[key] != value
    }
    unset_props = [key for key in old if key not in new]
    return set_props, unset_props
