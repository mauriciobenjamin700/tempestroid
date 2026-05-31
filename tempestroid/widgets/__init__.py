"""Typed, declarative widget primitives.

Widgets form the intermediate representation (IR): a tree of Pydantic models the
reconciler diffs and the leaf renderers apply. Import them from this package
level rather than from submodules.
"""

from tempestroid.widgets.base import (
    DateChangeHandler,
    EventHandler,
    FileSelectHandler,
    SlideHandler,
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
    SlideEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    parse_event,
)
from tempestroid.widgets.indicators import ProgressBar, Spinner
from tempestroid.widgets.inputs import (
    Checkbox,
    DatePicker,
    FilePicker,
    Input,
    KeyboardType,
    Slider,
    Switch,
    TextArea,
)
from tempestroid.widgets.layout import Column, Container, Row, ScrollView
from tempestroid.widgets.media import Icon, Image, ImageFit
from tempestroid.widgets.text import Text

__all__ = [
    "EventHandler",
    "TextChangeHandler",
    "ToggleHandler",
    "SlideHandler",
    "DateChangeHandler",
    "FileSelectHandler",
    "handler_accepts_event",
    "Widget",
    "Text",
    "Button",
    "Column",
    "Row",
    "Container",
    "ScrollView",
    "Input",
    "TextArea",
    "Checkbox",
    "Switch",
    "Slider",
    "KeyboardType",
    "DatePicker",
    "FilePicker",
    "Image",
    "ImageFit",
    "Icon",
    "ProgressBar",
    "Spinner",
    "Event",
    "TapEvent",
    "TextChangeEvent",
    "ToggleEvent",
    "SlideEvent",
    "DateChangeEvent",
    "FileSelectEvent",
    "EventValidationError",
    "parse_event",
]
