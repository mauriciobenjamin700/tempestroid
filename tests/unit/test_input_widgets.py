"""Tests for the value-bearing widgets (Input/Checkbox/DatePicker/FilePicker).

Covers the new typed events, the widget event contracts, the boundary
value-passing (a handler that accepts an argument receives the typed event,
while a zero-argument handler is still called bare), serialization of the value
scalars, introspection, and the Qt renderer wiring of the change signals.
"""

import asyncio

import pytest
from PySide6.QtWidgets import QCheckBox, QDateEdit, QLineEdit

from tempestroid import (
    App,
    Checkbox,
    Column,
    DateChangeEvent,
    DatePicker,
    EventValidationError,
    FilePicker,
    FileSelectEvent,
    Input,
    TextChangeEvent,
    ToggleEvent,
    build,
    introspect,
    parse_event,
)
from tempestroid.bridge import DeviceApp, EventMessage, LoopbackBridge, serialize_node
from tempestroid.renderers.qt import QtRenderer
from tempestroid.widgets import handler_accepts_event

# --- events ----------------------------------------------------------------


def test_toggle_event_round_trip():
    event = parse_event(ToggleEvent, {"checked": True})
    assert event.checked is True


def test_date_change_event_round_trip():
    event = parse_event(DateChangeEvent, {"value": "2026-05-30"})
    assert event.value == "2026-05-30"


def test_file_select_event_optional_name():
    event = parse_event(FileSelectEvent, {"uri": "content://x/a.pdf"})
    assert event.uri == "content://x/a.pdf"
    assert event.name is None


def test_toggle_event_rejects_missing_field():
    with pytest.raises(EventValidationError) as exc:
        parse_event(ToggleEvent, {})
    assert exc.value.event_type is ToggleEvent


# --- widget contracts ------------------------------------------------------


def test_widgets_declare_change_event_schemas():
    assert Input.event_schemas == {"on_change": TextChangeEvent}
    assert Checkbox.event_schemas == {"on_change": ToggleEvent}
    assert DatePicker.event_schemas == {"on_change": DateChangeEvent}
    assert FilePicker.event_schemas == {"on_select": FileSelectEvent}


def test_widget_defaults():
    assert Input().value == "" and Input().placeholder == ""
    assert Checkbox().checked is False
    assert DatePicker().value == ""
    assert FilePicker().label == "Choose file"


# --- handler arity ---------------------------------------------------------


def test_handler_accepts_event_detects_arity():
    def takes_one(event: object) -> object:
        return event

    def takes_none() -> None:
        return None

    assert handler_accepts_event(takes_one) is True
    assert handler_accepts_event(takes_none) is False
    assert handler_accepts_event(lambda: None) is False


# --- serialization ---------------------------------------------------------


def test_serialize_carries_value_scalars_and_tokens():
    node = build(
        Column(
            children=[
                Input(value="hi", placeholder="name", on_change=lambda e: e, key="i"),
                Checkbox(label="ok", checked=True, on_change=lambda e: e, key="c"),
            ]
        )
    )
    payload = serialize_node(node)
    input_props = payload["children"][0]["props"]
    assert input_props["value"] == "hi"
    assert input_props["placeholder"] == "name"
    assert input_props["on_change"]["event"] == "TextChangeEvent"
    checkbox_props = payload["children"][1]["props"]
    assert checkbox_props["checked"] is True
    assert checkbox_props["on_change"]["event"] == "ToggleEvent"


# --- introspection ---------------------------------------------------------


def test_introspection_includes_new_widgets_and_events():
    spec = introspect()
    for name in ("Input", "Checkbox", "DatePicker", "FilePicker"):
        assert name in spec["widgets"]
    for name in ("ToggleEvent", "DateChangeEvent", "FileSelectEvent"):
        assert name in spec["events"]


# --- bridge dispatch passes the typed event --------------------------------


def test_dispatch_passes_typed_value_to_handler():
    captured: dict[str, object] = {}

    class State:
        text: str = ""

    def view(app: App[State]) -> Column:
        return Column(
            children=[
                Input(
                    value=app.state.text,
                    on_change=lambda e: captured.__setitem__("value", e.value),
                    key="field",
                )
            ]
        )

    async def run() -> None:
        bridge = LoopbackBridge()
        device = DeviceApp(State(), view, bridge)
        await device.start()
        root = device.app.current_tree
        assert root is not None
        token = serialize_node(root)["children"][0]["props"]["on_change"]["$handler"]
        await device.handle_event(
            EventMessage(token=token, payload={"value": "typed"}).model_dump()
        )

    asyncio.run(run())
    assert captured["value"] == "typed"


# --- Qt renderer wiring ----------------------------------------------------


pytestmark = pytest.mark.usefixtures("qapp")


def test_qt_renders_input_and_emits_typed_value():
    captured: dict[str, object] = {}
    renderer = QtRenderer()
    host = renderer.mount(
        build(
            Input(
                value="start",
                placeholder="hint",
                on_change=lambda e: captured.__setitem__("text", e.value),
            )
        )
    )
    edit = host.findChildren(QLineEdit)[0]
    assert edit.text() == "start"
    assert edit.placeholderText() == "hint"
    edit.setText("edited")
    assert captured["text"] == "edited"


def test_qt_renders_checkbox_and_emits_toggle():
    captured: dict[str, object] = {}
    renderer = QtRenderer()
    host = renderer.mount(
        build(
            Checkbox(
                label="agree",
                checked=False,
                on_change=lambda e: captured.__setitem__("on", e.checked),
            )
        )
    )
    box = host.findChildren(QCheckBox)[0]
    box.setChecked(True)
    assert captured["on"] is True


def test_qt_renders_datepicker_and_emits_iso_date():
    captured: dict[str, object] = {}
    renderer = QtRenderer()
    host = renderer.mount(
        build(
            DatePicker(
                value="2026-05-30",
                on_change=lambda e: captured.__setitem__("date", e.value),
            )
        )
    )
    edit = host.findChildren(QDateEdit)[0]
    assert edit.date().toString("yyyy-MM-dd") == "2026-05-30"
    edit.setDate(edit.date().addDays(1))
    assert captured["date"] == "2026-05-31"


def test_qt_zero_arg_handler_still_called():
    calls: list[int] = []
    renderer = QtRenderer()
    host = renderer.mount(
        build(Checkbox(label="x", on_change=lambda: calls.append(1)))
    )
    host.findChildren(QCheckBox)[0].setChecked(True)
    assert calls == [1]
