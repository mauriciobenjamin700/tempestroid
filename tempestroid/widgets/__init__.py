"""Typed, declarative widget primitives.

Widgets form the intermediate representation (IR): a tree of Pydantic models the
reconciler diffs and the leaf renderers apply. Import them from this package
level rather than from submodules.
"""

from tempestroid.widgets.base import (
    Component,
    DateChangeHandler,
    EventHandler,
    FileSelectHandler,
    LongPressHandler,
    SlideHandler,
    SwipeHandler,
    TapHandler,
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
    LongPressEvent,
    SlideEvent,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    parse_event,
)
from tempestroid.widgets.gestures import GestureDetector
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
from tempestroid.widgets.layout import (
    Column,
    Container,
    Row,
    SafeArea,
    SafeAreaEdge,
    ScrollView,
    Stack,
)
from tempestroid.widgets.media import Icon, Image, ImageFit
from tempestroid.widgets.text import Text

__all__ = [
    "EventHandler",
    "TextChangeHandler",
    "ToggleHandler",
    "SlideHandler",
    "DateChangeHandler",
    "FileSelectHandler",
    "TapHandler",
    "LongPressHandler",
    "SwipeHandler",
    "handler_accepts_event",
    "Widget",
    "Component",
    "Text",
    "Button",
    "Column",
    "Row",
    "Container",
    "ScrollView",
    "SafeArea",
    "SafeAreaEdge",
    "Stack",
    "GestureDetector",
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
    "SwipeDirection",
    "LongPressEvent",
    "SwipeEvent",
    "EventValidationError",
    "parse_event",
]
