"""Serialize the IR (nodes) and reconciler patches for the wire.

Turns ``Node``/``Patch`` objects — which carry live Python values like ``Style``
and callables — into JSON-able dicts the device can apply:

* ``Style`` → the Compose spec dict (``Style → Compose``).
* handler callables → ``{"$handler": token, "event": EventName}`` (the device
  sends ``token`` back in an :class:`EventMessage`; the callable never crosses).
* plain scalars/containers → passed through; ``None`` props are dropped.

Path-addressed so handler tokens match what the registry computes from the same
tree (see ``protocol.handler_token``).
"""

from __future__ import annotations

from typing import Any, TypeGuard, cast

from tempestroid.bridge.protocol import event_type_for, handler_token
from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Path,
    Remove,
    Replace,
    Update,
)
from tempestroid.renderers.compose import to_compose
from tempestroid.style import Style
from tempestroid.widgets import MenuItem

__all__ = ["serialize_node", "serialize_patch"]

_JSON_SCALARS = (str, int, float, bool)


def _is_menu_item_list(value: Any) -> TypeGuard[list[MenuItem]]:  # noqa: ANN401 — narrows an untyped prop value
    """Narrow a prop value to a non-empty list of :class:`MenuItem`.

    Args:
        value: The candidate prop value.

    Returns:
        ``True`` when ``value`` is a non-empty list whose every element is a
        :class:`MenuItem`.
    """
    if not isinstance(value, list):
        return False
    items = cast("list[Any]", value)
    return len(items) > 0 and all(isinstance(item, MenuItem) for item in items)


def serialize_node(node: Node, path: Path = ()) -> dict[str, Any]:
    """Serialize an IR node (and its subtree) to a JSON-able dict.

    Args:
        node: The node to serialize.
        path: The node's path from the root (used for handler tokens).

    Returns:
        ``{"type", "key", "props", "children"}`` with all values JSON-safe.
    """
    return {
        "type": node.type,
        "key": node.key,
        "props": _serialize_props(node.type, node.props, path),
        "children": [
            serialize_node(child, path + (index,))
            for index, child in enumerate(node.children)
        ],
    }


def serialize_patch(patch: Patch) -> dict[str, Any]:
    """Serialize a single reconciler patch to a JSON-able dict.

    Args:
        patch: The patch to serialize.

    Returns:
        A tagged dict (``op`` field) the device can dispatch on.

    Raises:
        TypeError: If the patch is of an unknown type.
    """
    if isinstance(patch, Replace):
        return {"op": "replace", "path": list(patch.path),
                "node": serialize_node(patch.node, patch.path)}
    if isinstance(patch, Update):
        return {"op": "update", "path": list(patch.path),
                "set": _serialize_props(None, patch.set_props, patch.path),
                "unset": list(patch.unset_props)}
    if isinstance(patch, Insert):
        return {"op": "insert", "path": list(patch.path), "index": patch.index,
                "node": serialize_node(patch.node, patch.path + (patch.index,))}
    if isinstance(patch, Remove):
        return {"op": "remove", "path": list(patch.path), "index": patch.index}
    return {"op": "reorder", "path": list(patch.path), "order": list(patch.order)}


def _serialize_props(
    node_type: str | None,
    props: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    """Serialize a prop map: style → Compose spec, handlers → tokens, scalars pass.

    Args:
        node_type: The owning node's type (``None`` for a bare ``Update.set_props``
            where the type is unknown; handler event names are then omitted).
        props: The props to serialize.
        path: The owning node's path (for handler tokens).

    Returns:
        A JSON-able prop dict (``None`` values and non-serializable extras dropped).
    """
    out: dict[str, Any] = {}
    for name, value in props.items():
        if value is None:
            continue
        if name in ("item_builder", "header_builder"):
            # Virtualized-list factories are pure Python builders: they never
            # cross the boundary (the device iterates items natively). Drop them
            # before the generic callable branch treats them as handlers.
            continue
        if name == "validators":
            # FormField.validators is a list of pure-Python callables that run
            # entirely on the Python side (the host receives only the resulting
            # `error` string). The list is not JSON-serializable, so drop it
            # before the generic list branch would pass the callables through.
            continue
        if name == "sections":
            # SectionList.sections holds SectionHeader models carrying Python
            # builders (item_builder/header_builder) — not JSON-serializable. The
            # boundary only needs each section's metadata (title + item_count);
            # the visible widgets cross as the materialized window children.
            out[name] = [
                {"title": section.title, "item_count": section.item_count}
                for section in value
            ]
            continue
        if name == "commands":
            # Canvas.commands is a list of frozen DrawCommand value models; lower
            # each via model_dump() so the device gets plain dicts (every field is
            # JSON-safe — colors are [r, g, b, a] lists, never tuples).
            out[name] = [cmd.model_dump() for cmd in value]
            continue
        if name == "markers":
            # MapView.markers is already a list of JSON-safe dicts; pass it through.
            out[name] = value
            continue
        if name == "items" and _is_menu_item_list(value):
            # Menu/ActionSheet items are MenuItem value models; lower them to
            # plain dicts so the device gets the label/value/icon as JSON.
            out[name] = [
                {"label": item.label, "value": item.value, "icon": item.icon}
                for item in value
            ]
            continue
        if name == "semantics":
            # Lower the Semantics value model to its {label, role, hint} dict so
            # the device renderer (Compose `Modifier.semantics`) can read it; the
            # bare model would otherwise hit the drop-through below and never
            # cross, so accessibility labels would not reach the device a11y tree.
            out[name] = value.model_dump(exclude_none=True)
            continue
        if name == "style" and isinstance(value, Style):
            out[name] = to_compose(value)
        elif callable(value):
            ref: dict[str, Any] = {"$handler": handler_token(path, name)}
            event = event_type_for(node_type, name) if node_type else None
            if event is not None:
                ref["event"] = event.__name__
            out[name] = ref
        elif isinstance(value, tuple):
            # Virtualized lists carry their `window` as a (start, end) tuple;
            # JSON has no tuple, so it crosses as a 2-element array. Any other
            # tuple-valued prop normalizes to a list the same way.
            out[name] = list(cast("tuple[Any, ...]", value))
        elif isinstance(value, _JSON_SCALARS) or isinstance(value, (list, dict)):
            out[name] = value
        # Anything else is silently dropped — v1 widgets carry only the above.
    return out
