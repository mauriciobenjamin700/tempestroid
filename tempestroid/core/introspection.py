"""Introspection: a self-describing catalog of widgets, handlers and events.

Analogous to FastAPI's ``/docs``: it publishes the typed contract as plain,
JSON-serializable data — every widget's prop schema, the event each handler
emits, and every event payload schema. Tooling, the device bridge, and editors
can consume this to validate and autocomplete against the framework without
importing it.
"""

from __future__ import annotations

from typing import Any

from tempestroid.widgets import (
    Button,
    Checkbox,
    Column,
    Container,
    DateChangeEvent,
    DatePicker,
    Event,
    FilePicker,
    FileSelectEvent,
    GestureDetector,
    Icon,
    Image,
    Input,
    LongPressEvent,
    ProgressBar,
    Row,
    ScrollView,
    SlideEvent,
    Slider,
    Spinner,
    Stack,
    SwipeEvent,
    Switch,
    TapEvent,
    Text,
    TextArea,
    TextChangeEvent,
    ToggleEvent,
    Widget,
)

__all__ = [
    "WIDGET_TYPES",
    "EVENT_TYPES",
    "widget_catalog",
    "event_catalog",
    "introspect",
]

#: The widget types exposed by the framework, in a stable order.
WIDGET_TYPES: tuple[type[Widget], ...] = (
    Text,
    Button,
    Column,
    Row,
    Container,
    ScrollView,
    Stack,
    GestureDetector,
    Input,
    TextArea,
    Checkbox,
    Switch,
    Slider,
    DatePicker,
    FilePicker,
    Image,
    Icon,
    ProgressBar,
    Spinner,
)

#: The event payload types crossing the native boundary.
EVENT_TYPES: tuple[type[Event], ...] = (
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    SlideEvent,
    DateChangeEvent,
    FileSelectEvent,
    LongPressEvent,
    SwipeEvent,
)


def widget_catalog() -> dict[str, Any]:
    """Describe every widget: its prop schema and the events it emits.

    Returns:
        A mapping of widget name to ``{"schema": <json schema>, "events":
        {handler_prop: event_type_name}}``.
    """
    catalog: dict[str, Any] = {}
    for widget in WIDGET_TYPES:
        catalog[widget.__name__] = {
            "schema": widget.model_json_schema(),
            "events": {
                prop: event.__name__ for prop, event in widget.event_schemas.items()
            },
        }
    return catalog


def event_catalog() -> dict[str, Any]:
    """Describe every event payload schema.

    Returns:
        A mapping of event name to its JSON schema.
    """
    return {event.__name__: event.model_json_schema() for event in EVENT_TYPES}


def introspect() -> dict[str, Any]:
    """Produce the full, JSON-serializable framework contract.

    Returns:
        ``{"widgets": <widget catalog>, "events": <event catalog>}``.
    """
    return {"widgets": widget_catalog(), "events": event_catalog()}
