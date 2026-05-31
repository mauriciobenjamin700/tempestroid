"""Input widgets: ``Input``, ``Checkbox``, ``DatePicker`` and ``FilePicker``.

These are the value-bearing leaves of the IR. Each declares its change handler
in ``event_schemas`` so the boundary can validate the payload, and stores its
current value as a JSON scalar (``str``/``bool``) so the serializer carries it to
the device unchanged. The handler receives the validated typed event (it may
also be declared zero-argument when the value is not needed).
"""

from __future__ import annotations

from typing import ClassVar

from tempestroid.widgets.base import (
    DateChangeHandler,
    FileSelectHandler,
    TextChangeHandler,
    ToggleHandler,
    Widget,
)
from tempestroid.widgets.events import (
    DateChangeEvent,
    Event,
    FileSelectEvent,
    TextChangeEvent,
    ToggleEvent,
)

__all__ = ["Input", "Checkbox", "DatePicker", "FilePicker"]


class Input(Widget):
    """A single-line editable text field.

    Attributes:
        value: The current text value.
        placeholder: The hint shown when the field is empty.
        on_change: Handler invoked with a :class:`TextChangeEvent` on each edit.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": TextChangeEvent}

    value: str = ""
    placeholder: str = ""
    on_change: TextChangeHandler | None = None


class Checkbox(Widget):
    """A labelled boolean checkbox/switch.

    Attributes:
        label: The text shown beside the control.
        checked: Whether the box is currently checked.
        on_change: Handler invoked with a :class:`ToggleEvent` on toggle.
    """

    event_schemas: ClassVar[dict[str, type[Event]]] = {"on_change": ToggleEvent}

    label: str = ""
    checked: bool = False
    on_change: ToggleHandler | None = None


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
