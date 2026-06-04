"""Typed events and the boundary validation contract.

Without a WebView there is no JS↔Python frontier; the typed contract lives at
the Python↔Kotlin boundary. Events that come back from the native side (a tap, a
text change) arrive as raw payloads and must be validated *before* they enter a
Python handler — exactly like FastAPI validates a request body. These Pydantic
models are that contract, and :func:`parse_event` is the validation gate that
turns a raw payload into a typed event or raises a structured error.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "Event",
    "TapEvent",
    "TextChangeEvent",
    "ToggleEvent",
    "SlideEvent",
    "DateChangeEvent",
    "FileSelectEvent",
    "SwipeDirection",
    "LongPressEvent",
    "SwipeEvent",
    "RouteChangeEvent",
    "ScrollEvent",
    "RefreshEvent",
    "EndReachedEvent",
    "DismissEvent",
    "MenuSelectEvent",
    "EventValidationError",
    "parse_event",
]


class Event(BaseModel):
    """Base class for all events crossing the native boundary."""

    model_config = ConfigDict(frozen=True)


class TapEvent(Event):
    """A tap/click on a widget.

    Attributes:
        x: Optional x position of the tap, in logical pixels.
        y: Optional y position of the tap, in logical pixels.
    """

    x: float | None = None
    y: float | None = None


class TextChangeEvent(Event):
    """A text input's value changed.

    Attributes:
        value: The new text value.
        valid: Whether the value satisfies the input's ``pattern`` (regex), or
            ``None`` when the input declares no pattern. The renderer computes
            this against the widget's pattern before dispatch.
    """

    value: str
    valid: bool | None = None


class ToggleEvent(Event):
    """A checkbox/switch toggled.

    Attributes:
        checked: The new checked state.
    """

    checked: bool


class SlideEvent(Event):
    """A slider's value changed.

    Attributes:
        value: The new slider value, in the widget's ``[min, max]`` range.
    """

    value: float


class DateChangeEvent(Event):
    """A date picker's value changed.

    Attributes:
        value: The new date as an ISO ``yyyy-mm-dd`` string (empty when cleared).
    """

    value: str


class FileSelectEvent(Event):
    """A file was selected from a file picker.

    Attributes:
        uri: The selected file's URI (Android ``content://``) or path.
        name: The display name, if the platform reports one.
    """

    uri: str
    name: str | None = None


class SwipeDirection(StrEnum):
    """The cardinal direction of a swipe gesture."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class LongPressEvent(Event):
    """A press held past the long-press threshold.

    Attributes:
        x: Optional x position of the press, in logical pixels.
        y: Optional y position of the press, in logical pixels.
    """

    x: float | None = None
    y: float | None = None


class SwipeEvent(Event):
    """A directional swipe (a press-drag-release past the distance threshold).

    Attributes:
        direction: The dominant cardinal direction of the swipe.
        dx: Total horizontal travel from press to release, in logical pixels.
        dy: Total vertical travel from press to release, in logical pixels.
    """

    direction: SwipeDirection
    dx: float = 0.0
    dy: float = 0.0


class RouteChangeEvent(Event):
    """The active route changed (a push/pop/replace happened).

    This is the typed payload a navigation host emits when it settles on a new
    screen, so handlers (analytics, focus management) can react to navigation
    across the native boundary.

    Attributes:
        name: The destination route name.
        params: The destination route's typed parameters.
    """

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ScrollEvent(Event):
    """A scrollable container scrolled.

    Emitted by virtualized lists as the user scrolls, so the application can
    recompute the visible window and request new items.

    Attributes:
        offset: The current scroll position, in logical pixels.
        direction: The scroll axis (``"vertical"`` or ``"horizontal"``).
    """

    offset: float
    direction: str


class RefreshEvent(Event):
    """A pull-to-refresh gesture completed.

    Carries no payload: the gesture itself is the signal. The handler typically
    reloads the list's data and clears the widget's ``refreshing`` flag.
    """


class EndReachedEvent(Event):
    """The list scrolled past its end-reached threshold.

    Carries no payload. The handler typically paginates — loading the next page
    of items and growing the list's ``item_count``.
    """


class DismissEvent(Event):
    """An overlay was dismissed (barrier tap, swipe-down, or system back).

    The renderer emits this when the user dismisses an overlay through a gesture
    the host owns (tapping the scrim behind a dialog, dragging a sheet down). The
    bridge routes it to ``App.dismiss``; the optional ``overlay_id`` lets the
    host name the overlay, while ``None`` lets a renderer fire it without one
    (the bridge then falls back to the token-encoded id).

    Attributes:
        overlay_id: The dismissed overlay's stable id, or ``None`` when the
            renderer dispatches without one.
    """

    overlay_id: str | None = None


class MenuSelectEvent(Event):
    """The user selected an item from a menu or action sheet.

    Attributes:
        value: The selected item's stable value.
        label: The selected item's display label.
    """

    value: str
    label: str


E = TypeVar("E", bound=Event)


class EventValidationError(Exception):
    """Raised when a raw event payload fails validation at the boundary.

    Attributes:
        event_type: The expected event type.
        errors: The structured Pydantic error list (JSON-serializable).
    """

    def __init__(self, event_type: type[Event], errors: list[dict[str, Any]]) -> None:
        """Initialize the error.

        Args:
            event_type: The expected event type.
            errors: The structured validation errors.
        """
        self.event_type: type[Event] = event_type
        self.errors: list[dict[str, Any]] = errors
        super().__init__(
            f"invalid {event_type.__name__} payload: {errors}"
        )


def parse_event(event_type: type[E], raw: Mapping[str, Any]) -> E:
    """Validate a raw payload into a typed event.

    This is the boundary gate: native code sends an untyped mapping, and only a
    valid payload becomes a typed event the handler can trust.

    Args:
        event_type: The expected event type.
        raw: The raw payload from the native boundary.

    Returns:
        The validated, typed event.

    Raises:
        EventValidationError: If the payload does not match ``event_type``, with
            the structured field errors attached.
    """
    try:
        return event_type.model_validate(dict(raw))
    except ValidationError as exc:
        errors = cast("list[dict[str, Any]]", exc.errors())
        raise EventValidationError(event_type, errors) from exc
