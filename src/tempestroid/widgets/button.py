"""Button leaf widget."""

from __future__ import annotations

from typing import ClassVar

from tempestroid.widgets.base import EventHandler, Widget
from tempestroid.widgets.events import Event, TapEvent

__all__ = ["Button"]


class Button(Widget):
    """A tappable button.

    Attributes:
        label: The text shown on the button.
        on_click: Optional handler invoked on tap. May be sync or ``async``;
            the runtime schedules awaitables on the event loop.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_click": TapEvent}

    label: str
    on_click: EventHandler | None = None
