"""Tests for the expanded component gallery: utility widgets, input styling and
implicit ``Style`` transitions, across the IR, both translators, the serializer,
introspection and the Qt renderer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tempestroid import (
    Curve,
    Icon,
    Image,
    ImageFit,
    Input,
    KeyboardType,
    ProgressBar,
    ScrollView,
    SlideEvent,
    Slider,
    Spinner,
    Style,
    Switch,
    Text,
    TextArea,
    TextChangeEvent,
    Transition,
    build,
    event_catalog,
    parse_event,
    to_compose,
    widget_catalog,
)
from tempestroid.bridge import serialize_node
from tempestroid.bridge.protocol import EVENT_SCHEMAS

# --- IR: new widgets --------------------------------------------------------


def test_new_widget_type_tags() -> None:
    assert Slider().widget_type == "Slider"
    assert Switch().widget_type == "Switch"
    assert TextArea().widget_type == "TextArea"
    assert ProgressBar().widget_type == "ProgressBar"
    assert Spinner().widget_type == "Spinner"
    assert Image(src="a.png").widget_type == "Image"
    assert Icon(name="home").widget_type == "Icon"
    assert ScrollView().widget_type == "ScrollView"


def test_leaf_widgets_have_no_children() -> None:
    assert Slider().child_nodes() == []
    assert Switch().child_nodes() == []
    assert TextArea().child_nodes() == []
    assert ProgressBar().child_nodes() == []
    assert Spinner().child_nodes() == []
    assert Image(src="a.png").child_nodes() == []
    assert Icon(name="home").child_nodes() == []


def test_scrollview_exposes_children_in_order() -> None:
    view = ScrollView(children=[Text(content="a"), Text(content="b")], horizontal=True)
    assert [c.widget_type for c in view.child_nodes()] == ["Text", "Text"]
    assert view.horizontal is True


def test_slider_carries_range_and_value() -> None:
    slider = Slider(value=20.0, min_value=0.0, max_value=50.0, step=5.0)
    assert (slider.value, slider.min_value, slider.max_value, slider.step) == (
        20.0,
        0.0,
        50.0,
        5.0,
    )


def test_progressbar_value_is_clamped_to_unit_range() -> None:
    assert ProgressBar(value=0.5).value == 0.5
    with pytest.raises(ValidationError):
        ProgressBar(value=1.5)
    with pytest.raises(ValidationError):
        ProgressBar(value=-0.1)


def test_input_carries_styling_props() -> None:
    field = Input(
        secure=True, pattern=r"\d+", keyboard=KeyboardType.NUMBER, max_length=4
    )
    assert field.secure is True
    assert field.pattern == r"\d+"
    assert field.keyboard is KeyboardType.NUMBER
    assert field.max_length == 4


def test_image_fit_default_and_override() -> None:
    assert Image(src="a.png").fit is ImageFit.CONTAIN
    assert Image(src="a.png", fit=ImageFit.COVER).fit is ImageFit.COVER


# --- events -----------------------------------------------------------------


def test_slide_event_round_trip() -> None:
    event = SlideEvent(value=42.0)
    restored = parse_event(SlideEvent, event.model_dump())
    assert restored.value == 42.0


def test_text_change_event_valid_is_optional() -> None:
    assert TextChangeEvent(value="x").valid is None
    assert parse_event(TextChangeEvent, {"value": "x", "valid": True}).valid is True


# --- transitions / Style ----------------------------------------------------


def test_transition_requires_positive_duration() -> None:
    Transition(duration_ms=1)
    with pytest.raises(ValidationError):
        Transition(duration_ms=0)


def test_transition_is_frozen() -> None:
    transition = Transition(duration_ms=200)
    with pytest.raises(ValidationError):
        transition.duration_ms = 300  # type: ignore[misc]


def test_to_compose_emits_transition() -> None:
    spec = to_compose(
        Style(transition=Transition(duration_ms=250, curve=Curve.EASE_OUT, delay_ms=10))
    )
    assert spec["transition"] == {
        "durationMs": 250,
        "curve": "easeOut",
        "delayMs": 10,
    }


def test_to_compose_omits_transition_when_unset() -> None:
    assert "transition" not in to_compose(Style())


# --- serializer -------------------------------------------------------------


def test_serialize_slider_props_and_handler_token() -> None:
    node = build(
        Slider(value=3.0, min_value=0.0, max_value=10.0, on_change=lambda e: None)
    )
    data = serialize_node(node)
    assert data["props"]["value"] == 3.0
    assert data["props"]["min_value"] == 0.0
    handler = data["props"]["on_change"]
    assert handler["$handler"] == "root:on_change"
    assert handler["event"] == "SlideEvent"


def test_serialize_input_styling_scalars_pass_through() -> None:
    node = build(Input(secure=True, pattern=r"\d+", keyboard=KeyboardType.NUMBER))
    props = serialize_node(node)["props"]
    assert props["secure"] is True
    assert props["pattern"] == r"\d+"
    assert props["keyboard"] == "number"


# --- introspection / protocol ----------------------------------------------


def test_catalogs_list_new_surface() -> None:
    widgets = set(widget_catalog())
    assert {
        "Slider",
        "Switch",
        "TextArea",
        "ScrollView",
        "Image",
        "Icon",
        "ProgressBar",
        "Spinner",
    } <= widgets
    assert "SlideEvent" in event_catalog()


def test_event_schemas_cover_new_handlers() -> None:
    assert EVENT_SCHEMAS["Slider"] == {"on_change": SlideEvent}
    assert EVENT_SCHEMAS["Switch"]["on_change"].__name__ == "ToggleEvent"
    assert EVENT_SCHEMAS["TextArea"]["on_change"].__name__ == "TextChangeEvent"
