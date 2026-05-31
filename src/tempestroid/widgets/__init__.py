"""Typed, declarative widget primitives.

Widgets form the intermediate representation (IR): a tree of Pydantic models the
reconciler diffs and the leaf renderers apply. Import them from this package
level rather than from submodules.
"""

from tempestroid.widgets.base import (
    DateChangeHandler,
    EventHandler,
    FileSelectHandler,
    TextChangeHandler,
    ToggleHandler,
    Widget,
    handler_accepts_event,
)
from tempestroid.widgets.button import Button
from tempestroid.widgets.events import (
    DateChangeEvent,
    Event,
    EventValidationError,
    FileSelectEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    parse_event,
)
from tempestroid.widgets.inputs import Checkbox, DatePicker, FilePicker, Input
from tempestroid.widgets.layout import Column, Container, Row
from tempestroid.widgets.text import Text

__all__ = [
    "EventHandler",
    "TextChangeHandler",
    "ToggleHandler",
    "DateChangeHandler",
    "FileSelectHandler",
    "handler_accepts_event",
    "Widget",
    "Text",
    "Button",
    "Column",
    "Row",
    "Container",
    "Input",
    "Checkbox",
    "DatePicker",
    "FilePicker",
    "Event",
    "TapEvent",
    "TextChangeEvent",
    "ToggleEvent",
    "DateChangeEvent",
    "FileSelectEvent",
    "EventValidationError",
    "parse_event",
]
