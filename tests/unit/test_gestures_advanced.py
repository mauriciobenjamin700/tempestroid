"""Advanced-gesture (E4) IR/core coverage: build, serialize, parse, contract.

Exercises the renderer-agnostic half of the advanced gestures end to end: each
widget builds into the expected IR node, the serializer lowers its handler to a
path token carrying the event-type name, every new event validates at the
boundary, and the protocol/introspection catalogs expose the full contract. No
renderer is touched here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tempestroid import (
    Dismissible,
    DoubleTapHandler,
    DragEvent,
    Draggable,
    DragTarget,
    InteractiveViewer,
    PanEvent,
    PanHandler,
    ReorderableList,
    ReorderEvent,
    ScaleEvent,
    ScaleHandler,
    SwipeDirection,
    Text,
    build,
    parse_event,
    serialize_node,
)
from tempestroid.bridge.protocol import event_type_for
from tempestroid.widgets import EventValidationError

# --- build: every widget lowers to the expected IR node ---------------------


def test_pan_handler_builds_with_child_and_handler() -> None:
    node = build(PanHandler(on_pan=lambda e: None, child=Text(content="x")))
    assert node.type == "PanHandler"
    assert len(node.children) == 1 and node.children[0].type == "Text"
    assert callable(node.props["on_pan"])


def test_scale_handler_builds_with_both_handlers() -> None:
    node = build(
        ScaleHandler(
            on_scale=lambda e: None,
            on_double_tap=lambda: None,
            child=Text(content="img"),
        )
    )
    assert node.type == "ScaleHandler"
    assert callable(node.props["on_scale"])
    assert callable(node.props["on_double_tap"])


def test_double_tap_handler_builds() -> None:
    node = build(
        DoubleTapHandler(on_double_tap=lambda e: None, child=Text(content="x"))
    )
    assert node.type == "DoubleTapHandler"
    assert callable(node.props["on_double_tap"])


def test_draggable_carries_drag_data() -> None:
    node = build(
        Draggable(drag_data="item-3", on_drag=lambda e: None, child=Text(content="x"))
    )
    assert node.type == "Draggable"
    assert node.props["drag_data"] == "item-3"
    assert callable(node.props["on_drag"])


def test_drag_target_builds() -> None:
    node = build(DragTarget(on_drop=lambda e: None, child=Text(content="bin")))
    assert node.type == "DragTarget"
    assert callable(node.props["on_drop"])


def test_dismissible_builds_with_direction() -> None:
    node = build(
        Dismissible(
            direction=SwipeDirection.UP,
            on_dismiss=lambda e: None,
            child=Text(content="row"),
        )
    )
    assert node.type == "Dismissible"
    assert node.props["direction"] == "up"


def test_reorderable_list_builds_children_in_order() -> None:
    node = build(
        ReorderableList(
            on_reorder=lambda e: None,
            children=[Text(content="a"), Text(content="b")],
        )
    )
    assert node.type == "ReorderableList"
    assert [c.props["content"] for c in node.children] == ["a", "b"]
    assert callable(node.props["on_reorder"])


def test_interactive_viewer_builds_with_scale_bounds() -> None:
    node = build(
        InteractiveViewer(
            min_scale=0.25,
            max_scale=8.0,
            on_interaction=lambda e: None,
            child=Text(content="img"),
        )
    )
    assert node.type == "InteractiveViewer"
    assert node.props["min_scale"] == 0.25
    assert node.props["max_scale"] == 8.0
    assert callable(node.props["on_interaction"])


# --- serialize: handler props lower to a path token + event name ------------


@pytest.mark.parametrize(
    ("widget", "prop", "event_name"),
    [
        (
            PanHandler(on_pan=lambda e: None, child=Text(content="x")),
            "on_pan",
            "PanEvent",
        ),
        (
            ScaleHandler(on_scale=lambda e: None, child=Text(content="x")),
            "on_scale",
            "ScaleEvent",
        ),
        (
            DoubleTapHandler(on_double_tap=lambda e: None, child=Text(content="x")),
            "on_double_tap",
            "TapEvent",
        ),
        (
            Draggable(on_drag=lambda e: None, child=Text(content="x")),
            "on_drag",
            "DragEvent",
        ),
        (
            DragTarget(on_drop=lambda e: None, child=Text(content="x")),
            "on_drop",
            "DragEvent",
        ),
        (
            Dismissible(on_dismiss=lambda e: None, child=Text(content="x")),
            "on_dismiss",
            "DismissEvent",
        ),
        (
            ReorderableList(on_reorder=lambda e: None, children=[Text(content="x")]),
            "on_reorder",
            "ReorderEvent",
        ),
        (
            InteractiveViewer(on_interaction=lambda e: None, child=Text(content="x")),
            "on_interaction",
            "ScaleEvent",
        ),
    ],
)
def test_serializer_lowers_handler_to_token(
    widget: object, prop: str, event_name: str
) -> None:
    payload = serialize_node(build(widget))  # type: ignore[arg-type]
    ref = payload["props"][prop]
    assert ref["$handler"] == f"root:{prop}"
    assert ref["event"] == event_name


# --- parse_event: every new event validates at the boundary -----------------


def test_parse_events_validate() -> None:
    pan = parse_event(PanEvent, {"dx": 1.0, "dy": 2.0, "vx": 3.0, "vy": 4.0})
    assert (pan.dx, pan.dy, pan.vx, pan.vy) == (1.0, 2.0, 3.0, 4.0)
    scale = parse_event(
        ScaleEvent, {"scale": 2.0, "focus_x": 1.0, "focus_y": 2.0, "rotation": 90.0}
    )
    assert scale.scale == 2.0 and scale.rotation == 90.0
    drag = parse_event(DragEvent, {"data": "card", "x": 1.0, "y": 2.0})
    assert drag.data == "card"
    reorder = parse_event(ReorderEvent, {"from_index": 3, "to_index": 1})
    assert (reorder.from_index, reorder.to_index) == (3, 1)


def test_parse_reorder_rejects_non_int() -> None:
    with pytest.raises(EventValidationError):
        parse_event(ReorderEvent, {"from_index": "x", "to_index": 0})


# --- contract: no widget/prop pair returns None from event_type_for ---------


def test_no_event_type_for_returns_none_for_new_pairs() -> None:
    pairs = {
        "PanHandler": ["on_pan"],
        "ScaleHandler": ["on_scale", "on_double_tap"],
        "DoubleTapHandler": ["on_double_tap"],
        "Draggable": ["on_drag"],
        "DragTarget": ["on_drop"],
        "Dismissible": ["on_dismiss"],
        "ReorderableList": ["on_reorder"],
        "InteractiveViewer": ["on_interaction"],
    }
    for widget, props in pairs.items():
        for prop in props:
            assert event_type_for(widget, prop) is not None, (widget, prop)


def test_events_are_frozen() -> None:
    event = PanEvent(dx=1.0)
    with pytest.raises(ValidationError):
        event.dx = 2.0  # type: ignore[misc]
