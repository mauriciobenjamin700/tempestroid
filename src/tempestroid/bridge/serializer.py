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

from typing import Any

from tempestroid.bridge.protocol import event_type_for, handler_token
from tempestroid.core.ir import (
    Insert,
    Node,
    Patch,
    Remove,
    Replace,
    Update,
)
from tempestroid.renderers.compose import to_compose
from tempestroid.style import Style

__all__ = ["serialize_node", "serialize_patch"]

_JSON_SCALARS = (str, int, float, bool)


def serialize_node(node: Node, path: tuple[int, ...] = ()) -> dict[str, Any]:
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
    path: tuple[int, ...],
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
        if name == "style" and isinstance(value, Style):
            out[name] = to_compose(value)
        elif callable(value):
            ref: dict[str, Any] = {"$handler": handler_token(path, name)}
            event = event_type_for(node_type, name) if node_type else None
            if event is not None:
                ref["event"] = event.__name__
            out[name] = ref
        elif isinstance(value, _JSON_SCALARS) or isinstance(value, (list, dict)):
            out[name] = value
        # Anything else is silently dropped — v1 widgets carry only the above.
    return out
