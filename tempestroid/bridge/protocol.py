"""Wire protocol for the Python↔Kotlin boundary.

Messages cross a single marshalling boundary (the JNI bridge on the device, an
in-memory channel in tests). Outgoing messages (``mount``/``patch``) tell the
device what to render; the incoming ``event`` message carries a tap/text payload
back, addressed by a **handler token**.

A handler token identifies a handler by its node's **path** in the tree plus the
prop name (e.g. ``"0/1:on_click"``). Path-based (not key-based) so the emit side
(serializer) and the dispatch side (registry) compute identical tokens from the
same tree — they only need to agree within one rebuild, and every rebuild
re-sends. Tokens are stable for the lifetime of a tree shape; a reorder reshuffles
them and the accompanying patches carry the new wiring.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from tempestroid.widgets import (
    Button,
    Checkbox,
    Column,
    Container,
    DatePicker,
    Event,
    FilePicker,
    Icon,
    Image,
    Input,
    ProgressBar,
    Row,
    ScrollView,
    Slider,
    Spinner,
    Switch,
    Text,
    TextArea,
)

__all__ = [
    "handler_token",
    "event_type_for",
    "EVENT_SCHEMAS",
    "MountMessage",
    "PatchMessage",
    "EventMessage",
]

#: ``{widget_type: {handler_prop: event_type}}`` derived from each widget's
#: ``event_schemas`` classvar — the contract used to validate event payloads.
EVENT_SCHEMAS: dict[str, dict[str, type[Event]]] = {
    widget.__name__: dict(widget.event_schemas)
    for widget in (
        Text,
        Button,
        Column,
        Row,
        Container,
        ScrollView,
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
    if widget.event_schemas
}


def handler_token(path: tuple[int, ...], prop: str) -> str:
    """Build the stable token addressing a handler at ``path``/``prop``.

    Args:
        path: The node's path (child indices from the root).
        prop: The handler prop name (e.g. ``"on_click"``).

    Returns:
        A token like ``"root:on_click"`` or ``"0/2:on_click"``.
    """
    location = "/".join(str(index) for index in path) if path else "root"
    return f"{location}:{prop}"


def event_type_for(widget_type: str, prop: str) -> type[Event] | None:
    """Look up the event type a widget's handler prop emits.

    Args:
        widget_type: The widget type tag (e.g. ``"Button"``).
        prop: The handler prop name.

    Returns:
        The event type, or ``None`` if the widget/prop emits no typed event.
    """
    return EVENT_SCHEMAS.get(widget_type, {}).get(prop)


class MountMessage(BaseModel):
    """Initial render: the full serialized tree."""

    model_config = ConfigDict(frozen=True)

    kind: str = "mount"
    root: dict[str, Any]


class PatchMessage(BaseModel):
    """Incremental update: a list of serialized patches."""

    model_config = ConfigDict(frozen=True)

    kind: str = "patch"
    patches: list[dict[str, Any]]


class EventMessage(BaseModel):
    """An event coming back from the device, addressed by handler token.

    Attributes:
        token: The handler token (see :func:`handler_token`).
        payload: The raw event payload, validated on dispatch.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = "event"
    token: str
    payload: dict[str, Any] = {}
