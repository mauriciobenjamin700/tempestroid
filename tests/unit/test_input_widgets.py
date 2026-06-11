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
    Autocomplete,
    Checkbox,
    Column,
    DateChangeEvent,
    DatePicker,
    Dropdown,
    EventValidationError,
    FilePicker,
    FileSelectEvent,
    Input,
    MaskedInput,
    PinInput,
    RangeChangeEvent,
    RangeSlider,
    SelectEvent,
    SubmitEvent,
    TextChangeEvent,
    TimeChangeEvent,
    TimePicker,
    ToggleEvent,
    build,
    introspect,
    parse_event,
)
from tempestroid.bridge import DeviceApp, EventMessage, LoopbackBridge, serialize_node
from tempestroid.bridge.protocol import event_type_for
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


# --- E5 controls: events ----------------------------------------------------


def test_select_event_round_trip_and_rejection():
    event = parse_event(SelectEvent, {"value": "Brazil", "index": 1})
    assert event.value == "Brazil"
    assert event.index == 1
    with pytest.raises(EventValidationError):
        parse_event(SelectEvent, {"value": "Brazil"})  # missing index


def test_time_change_event_round_trip():
    event = parse_event(TimeChangeEvent, {"value": "09:45"})
    assert event.value == "09:45"


def test_range_change_event_round_trip():
    event = parse_event(RangeChangeEvent, {"low": 5.0, "high": 50.0})
    assert event.low == 5.0
    assert event.high == 50.0


def test_submit_event_round_trip():
    event = parse_event(SubmitEvent, {"values": {"otp": "1234"}})
    assert event.values == {"otp": "1234"}


# --- E5 controls: widget contracts ------------------------------------------


def test_e5_widgets_declare_event_schemas():
    assert Dropdown.event_schemas == {"on_select": SelectEvent}
    assert TimePicker.event_schemas == {"on_change": TimeChangeEvent}
    assert RangeSlider.event_schemas == {"on_change": RangeChangeEvent}
    assert Autocomplete.event_schemas == {
        "on_change": TextChangeEvent,
        "on_select": SelectEvent,
    }
    assert PinInput.event_schemas == {
        "on_change": TextChangeEvent,
        "on_complete": SubmitEvent,
    }
    assert MaskedInput.event_schemas == {"on_change": TextChangeEvent}


def test_e5_widget_defaults():
    assert Dropdown().options == [] and Dropdown().value is None
    assert TimePicker().value == ""
    assert RangeSlider().low == 0.0 and RangeSlider().high == 100.0
    assert PinInput().length == 6
    assert MaskedInput().mask == ""


# --- E5 controls: bridge event-type resolution ------------------------------


def test_event_type_for_resolves_e5_widgets():
    assert event_type_for("Dropdown", "on_select") is SelectEvent
    assert event_type_for("TimePicker", "on_change") is TimeChangeEvent
    assert event_type_for("RangeSlider", "on_change") is RangeChangeEvent
    assert event_type_for("PinInput", "on_complete") is SubmitEvent
    assert event_type_for("PinInput", "on_change") is TextChangeEvent
    assert event_type_for("Autocomplete", "on_select") is SelectEvent
    assert event_type_for("Autocomplete", "on_change") is TextChangeEvent
    assert event_type_for("MaskedInput", "on_change") is TextChangeEvent


# --- E5 controls: serialization ---------------------------------------------


def test_serialize_dropdown_carries_options_and_token():
    node = build(
        Dropdown(options=["BR", "US"], value="BR", on_select=lambda e: e, key="d")
    )
    payload = serialize_node(node)
    assert payload["props"]["options"] == ["BR", "US"]
    assert payload["props"]["value"] == "BR"
    assert payload["props"]["on_select"]["event"] == "SelectEvent"


def test_serialize_range_slider_carries_float_bounds():
    node = build(RangeSlider(low=10.0, high=80.0, on_change=lambda e: e, key="r"))
    payload = serialize_node(node)
    assert payload["props"]["low"] == 10.0
    assert payload["props"]["high"] == 80.0
    assert payload["props"]["on_change"]["event"] == "RangeChangeEvent"


def test_serialize_autocomplete_carries_both_handler_tokens():
    node = build(
        Autocomplete(
            options=["a", "ab"],
            on_change=lambda e: e,
            on_select=lambda e: e,
            key="ac",
        )
    )
    payload = serialize_node(node)
    assert payload["props"]["on_change"]["event"] == "TextChangeEvent"
    assert payload["props"]["on_select"]["event"] == "SelectEvent"
    assert (
        payload["props"]["on_change"]["$handler"]
        != payload["props"]["on_select"]["$handler"]
    )


def test_serialize_pin_input_carries_change_and_complete_tokens():
    node = build(
        PinInput(length=4, on_change=lambda e: e, on_complete=lambda e: e, key="p")
    )
    payload = serialize_node(node)
    assert payload["props"]["length"] == 4
    assert payload["props"]["on_change"]["event"] == "TextChangeEvent"
    assert payload["props"]["on_complete"]["event"] == "SubmitEvent"


def test_serialize_masked_input_carries_mask():
    node = build(MaskedInput(mask="999.999.999-99", on_change=lambda e: e, key="m"))
    payload = serialize_node(node)
    assert payload["props"]["mask"] == "999.999.999-99"
    assert payload["props"]["on_change"]["event"] == "TextChangeEvent"


# --- E5 controls: introspection ---------------------------------------------


def test_introspection_includes_e5_widgets_and_events():
    spec = introspect()
    for name in (
        "Dropdown",
        "TimePicker",
        "RangeSlider",
        "Autocomplete",
        "PinInput",
        "MaskedInput",
    ):
        assert name in spec["widgets"]
    for name in (
        "SelectEvent",
        "TimeChangeEvent",
        "RangeChangeEvent",
        "SubmitEvent",
        "ValidationEvent",
    ):
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
        scene = device.app.current_tree
        assert scene is not None
        token = serialize_node(scene.root)["children"][0]["props"]["on_change"][
            "$handler"
        ]
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
    host = renderer.mount(build(Checkbox(label="x", on_change=lambda: calls.append(1))))
    host.findChildren(QCheckBox)[0].setChecked(True)
    assert calls == [1]
