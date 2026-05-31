"""Input widgets: text fields, selection controls and value sliders.

These are the value-bearing leaves of the IR. Each declares its change handler
in ``event_schemas`` so the boundary can validate the payload, and stores its
current value as a JSON scalar (``str``/``bool``/``float``) so the serializer
carries it to the device unchanged. The handler receives the validated typed
event (it may also be declared zero-argument when the value is not needed).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from tempestroid.widgets.base import (
    DateChangeHandler,
    FileSelectHandler,
    SlideHandler,
    TextChangeHandler,
    ToggleHandler,
    Widget,
)
from tempestroid.widgets.events import (
    DateChangeEvent,
    Event,
    FileSelectEvent,
    SlideEvent,
    TextChangeEvent,
    ToggleEvent,
)

__all__ = [
    "KeyboardType",
    "Input",
    "TextArea",
    "Checkbox",
    "Switch",
    "Slider",
    "DatePicker",
    "FilePicker",
]


class KeyboardType(StrEnum):
    """The soft-keyboard variant a text field requests on the device.

    Maps to Android ``inputType`` on the device renderer and to Qt input-method
    hints in the simulator.
    """

    TEXT = "text"
    NUMBER = "number"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    PASSWORD = "password"


class Input(Widget):
    """A single-line editable text field.

    Attributes:
        value: The current text value.
        placeholder: The hint shown when the field is empty.
        secure: Whether the text is masked (password field). When set, the
            renderer also offers a visibility toggle ("eye") that reveals the
            text locally without a round-trip to Python.
        pattern: An optional regular expression the value must fully match to be
            considered valid. The renderer evaluates it and reports the result
            via :attr:`TextChangeEvent.valid`.
        error: An optional validation message shown when the value is invalid.
        keyboard: The soft-keyboard variant the field requests.
        max_length: An optional cap on the number of characters.
        on_change: Handler invoked with a :class:`TextChangeEvent` on each edit.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": TextChangeEvent}

    value: str = ""
    placeholder: str = ""
    secure: bool = False
    pattern: str | None = None
    error: str = ""
    keyboard: KeyboardType = KeyboardType.TEXT
    max_length: int | None = None
    on_change: TextChangeHandler | None = None


class TextArea(Widget):
    """A multi-line editable text field.

    Attributes:
        value: The current text value.
        placeholder: The hint shown when the field is empty.
        rows: The number of visible text rows (initial height hint).
        max_length: An optional cap on the number of characters.
        on_change: Handler invoked with a :class:`TextChangeEvent` on each edit.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": TextChangeEvent}

    value: str = ""
    placeholder: str = ""
    rows: int = 3
    max_length: int | None = None
    on_change: TextChangeHandler | None = None


class Checkbox(Widget):
    """A labelled boolean checkbox.

    Attributes:
        label: The text shown beside the control.
        checked: Whether the box is currently checked.
        on_change: Handler invoked with a :class:`ToggleEvent` on toggle.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": ToggleEvent}

    label: str = ""
    checked: bool = False
    on_change: ToggleHandler | None = None


class Switch(Widget):
    """A labelled on/off switch (toggle).

    Distinct from :class:`Checkbox` only in its rendered affordance — both carry
    the same boolean semantics.

    Attributes:
        label: The text shown beside the control.
        checked: Whether the switch is currently on.
        on_change: Handler invoked with a :class:`ToggleEvent` on toggle.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": ToggleEvent}

    label: str = ""
    checked: bool = False
    on_change: ToggleHandler | None = None


class Slider(Widget):
    """A draggable value slider over a numeric range.

    Attributes:
        value: The current value, clamped to ``[min_value, max_value]``.
        min_value: The lowest selectable value.
        max_value: The highest selectable value.
        step: The increment between selectable values.
        on_change: Handler invoked with a :class:`SlideEvent` as the value moves.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": SlideEvent}

    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    on_change: SlideHandler | None = None


class DatePicker(Widget):
    """A date selection field.

    Attributes:
        value: The selected date as an ISO ``yyyy-mm-dd`` string (``""`` if unset).
        label: An optional label shown with the field.
        on_change: Handler invoked with a :class:`DateChangeEvent` on selection.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": DateChangeEvent}

    value: str = ""
    label: str = ""
    on_change: DateChangeHandler | None = None


class FilePicker(Widget):
    """A button that opens the platform file picker.

    Attributes:
        label: The button text.
        value: The selected file's display name/URI (``""`` until one is chosen).
        on_select: Handler invoked with a :class:`FileSelectEvent` on selection.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_select": FileSelectEvent}

    label: str = "Choose file"
    value: str = ""
    on_select: FileSelectHandler | None = None
