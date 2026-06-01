"""Handler registry: map tokens to live callables and dispatch typed events.

The serializer sends handler **tokens** to the device. When the device sends an
event back, this registry resolves the token to the current Python callable,
**validates the payload** against the widget's declared event type (the A6
boundary contract), then invokes the handler. It is refreshed from the current
tree on every rebuild, so tokens always resolve to the latest callables.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from tempestroid.bridge.protocol import event_type_for, handler_token
from tempestroid.core.ir import Node, Path, Scene
from tempestroid.widgets import Event, handler_accepts_event, parse_event

__all__ = ["HandlerRegistry"]

#: The reserved leading path step that addresses a scene's overlay layer.
_OVERLAY_STEP = "overlay"


def _invoke(handler: Callable[..., Any], event: Event | None) -> Any:  # noqa: ANN401 — handler return is arbitrary (a value or a coroutine to await)
    """Call a handler, passing the typed event only if it accepts one.

    Args:
        handler: The resolved handler callable.
        event: The validated event, or ``None`` when the widget emits no typed
            event.

    Returns:
        The handler's return value (possibly a coroutine to await).
    """
    if event is not None and handler_accepts_event(handler):
        return handler(event)
    return handler()


class HandlerRegistry:
    """Resolves handler tokens to callables and dispatches validated events."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._handlers: dict[str, tuple[Callable[[], Any], type[Event] | None]] = {}

    def refresh(self, root: Node | Scene | None) -> None:
        """Rebuild the token→handler map by walking the current tree.

        Accepts either a bare root :class:`Node` (legacy/no-overlay path) or a
        full :class:`Scene`. For a scene, the root is walked at ``()`` and each
        overlay at the reserved ``("overlay", i)`` prefix, so overlay handler
        tokens (e.g. ``"overlay/0:on_dismiss"``) match what the serializer emits.

        Args:
            root: The current root node, scene, or ``None`` to clear.
        """
        self._handlers.clear()
        if root is None:
            return
        if isinstance(root, Scene):
            self._walk(root.root, ())
            for index, overlay in enumerate(root.overlays):
                self._walk(overlay, (_OVERLAY_STEP, index))
            return
        self._walk(root, ())

    def _walk(self, node: Node, path: Path) -> None:
        """Register every handler prop on ``node`` and recurse.

        Args:
            node: The node to inspect.
            path: The node's path from the root.
        """
        for name, value in node.props.items():
            if callable(value):
                token = handler_token(path, name)
                self._handlers[token] = (value, event_type_for(node.type, name))
        for index, child in enumerate(node.children):
            self._walk(child, path + (index,))

    async def dispatch(self, token: str, payload: dict[str, Any]) -> bool:
        """Validate a payload and invoke the handler for ``token``.

        Args:
            token: The handler token from an :class:`EventMessage`.
            payload: The raw event payload.

        Returns:
            ``True`` if a handler was found and invoked, ``False`` otherwise.

        Raises:
            EventValidationError: If the payload fails validation for the
                handler's declared event type.
        """
        entry = self._handlers.get(token)
        if entry is None:
            return False
        handler, event_type = entry
        event: Event | None = None
        if event_type is not None:
            # Validate at the boundary before entering the handler (A6 contract).
            event = parse_event(event_type, payload)
        result = _invoke(handler, event)
        if inspect.iscoroutine(result):
            await result
        return True

    def tokens(self) -> list[str]:
        """Return the currently registered tokens (for inspection/tests).

        Returns:
            The registered handler tokens.
        """
        return list(self._handlers)
