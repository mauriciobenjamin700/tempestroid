"""Gesture detection: wrap a child and report taps, long-presses and swipes.

``GestureDetector`` is the framework's touch-gesture primitive. It is a single
-child container that renders its child untouched but watches the pointer over
it, turning press/drag/release sequences into typed events:

* ``on_tap`` / ``on_double_tap`` → :class:`~tempestroid.widgets.events.TapEvent`
* ``on_long_press`` → :class:`~tempestroid.widgets.events.LongPressEvent`
* ``on_swipe`` → :class:`~tempestroid.widgets.events.SwipeEvent` (carrying the
  dominant cardinal direction and total travel)

Both leaf renderers realize the same contract: Qt via a pointer event filter,
Compose via ``Modifier.pointerInput`` (``detectTapGestures`` + drag detection).
Gestures are best wrapped around non-interactive content (a card, an image, a
row of text); a child that consumes the pointer itself (e.g. a ``Button``) keeps
its own handling — that is a documented v1 limit.
"""

from __future__ import annotations

from typing import ClassVar

from tempestroid.widgets.base import (
    LongPressHandler,
    SwipeHandler,
    TapHandler,
    Widget,
)
from tempestroid.widgets.events import Event, LongPressEvent, SwipeEvent, TapEvent

__all__ = ["GestureDetector"]


class GestureDetector(Widget):
    """A single-child container that reports touch gestures over its child.

    Attributes:
        child: The wrapped widget the gestures are detected over.
        on_tap: Optional handler for a single tap (receives a ``TapEvent``).
        on_double_tap: Optional handler for a double tap (receives a ``TapEvent``).
        on_long_press: Optional handler for a held press past the long-press
            threshold (receives a ``LongPressEvent``).
        on_swipe: Optional handler for a directional swipe (receives a
            ``SwipeEvent``).
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {
        "on_tap": TapEvent,
        "on_double_tap": TapEvent,
        "on_long_press": LongPressEvent,
        "on_swipe": SwipeEvent,
    }
    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})

    child: Widget | None = None
    on_tap: TapHandler | None = None
    on_double_tap: TapHandler | None = None
    on_long_press: LongPressHandler | None = None
    on_swipe: SwipeHandler | None = None

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []
