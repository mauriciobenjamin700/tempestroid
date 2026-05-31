"""Overlay/stacking (``Stack``) and gesture (``GestureDetector``) coverage.

Exercises the new surface end to end: the widgets build into the expected IR,
the new events validate at the boundary, the ``Style → Compose`` translator
lowers the stacking fields, the serializer carries the gesture handler tokens,
and the Qt renderer lays out overlapping layers and classifies pointer gestures.
"""

# This suite deliberately reaches into renderer internals (_StackWidget /
# _GestureWidget / _at / _fire_long_press) to assert Qt geometry, and wires
# throwaway event lambdas + pytest.approx; relax the matching strict rules here.
# pyright: reportPrivateUsage=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from tempestroid import (
    GestureDetector,
    LongPressEvent,
    Position,
    Stack,
    StackAlign,
    Style,
    SwipeDirection,
    SwipeEvent,
    TapEvent,
    Text,
    build,
    diff,
    introspect,
    parse_event,
    serialize_node,
    to_compose,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import _GestureWidget, _StackWidget
from tempestroid.widgets import EventValidationError

# --- widgets / IR -----------------------------------------------------------


def test_stack_builds_with_ordered_children() -> None:
    node = build(Stack(children=[Text(content="bottom"), Text(content="top")]))
    assert node.type == "Stack"
    assert [child.props["content"] for child in node.children] == ["bottom", "top"]


def test_gesture_detector_builds_with_child_and_handlers() -> None:
    node = build(
        GestureDetector(
            on_tap=lambda: None,
            on_swipe=lambda e: None,
            child=Text(content="x"),
        )
    )
    assert node.type == "GestureDetector"
    assert len(node.children) == 1 and node.children[0].type == "Text"
    assert callable(node.props["on_tap"])
    assert callable(node.props["on_swipe"])


def test_gesture_detector_declares_its_event_contract() -> None:
    assert GestureDetector.event_schemas == {
        "on_tap": TapEvent,
        "on_double_tap": TapEvent,
        "on_long_press": LongPressEvent,
        "on_swipe": SwipeEvent,
    }


def test_introspection_lists_new_widgets_and_events() -> None:
    catalog = introspect()
    assert "Stack" in catalog["widgets"]
    assert "GestureDetector" in catalog["widgets"]
    assert "LongPressEvent" in catalog["events"]
    assert "SwipeEvent" in catalog["events"]


# --- events -----------------------------------------------------------------


def test_parse_swipe_event_validates_direction() -> None:
    event = parse_event(SwipeEvent, {"direction": "left", "dx": -50.0, "dy": 1.0})
    assert event.direction is SwipeDirection.LEFT
    assert event.dx == -50.0


def test_parse_swipe_event_rejects_bad_direction() -> None:
    with pytest.raises(EventValidationError):
        parse_event(SwipeEvent, {"direction": "sideways"})


def test_parse_long_press_event_defaults() -> None:
    event = parse_event(LongPressEvent, {})
    assert event.x is None and event.y is None


# --- style / compose translator --------------------------------------------


def test_style_keeps_stacking_fields_through_merge() -> None:
    base = Style(stack_align=StackAlign.CENTER)
    merged = base.merge(Style(position=Position.ABSOLUTE, top=4))
    assert merged.stack_align is StackAlign.CENTER
    assert merged.position is Position.ABSOLUTE
    assert merged.top == 4


def test_to_compose_lowers_stack_align() -> None:
    assert to_compose(Style(stack_align=StackAlign.BOTTOM_END)) == {
        "stackAlign": "bottomEnd"
    }


def test_to_compose_lowers_absolute_insets() -> None:
    spec = to_compose(
        Style(position=Position.ABSOLUTE, top=0, left=4, right=8, bottom=2)
    )
    assert spec == {
        "position": "absolute",
        "top": 0.0,
        "left": 4.0,
        "right": 8.0,
        "bottom": 2.0,
    }


# --- serializer -------------------------------------------------------------


def test_serializer_carries_gesture_tokens_and_event_names() -> None:
    node = build(GestureDetector(on_swipe=lambda e: None, child=Text(content="x")))
    payload = serialize_node(node)
    ref = payload["props"]["on_swipe"]
    assert ref["$handler"] == "root:on_swipe"
    assert ref["event"] == "SwipeEvent"


# --- Qt renderer: stacking --------------------------------------------------


@pytest.mark.usefixtures("qapp")
class TestQtStack:
    def test_stack_mounts_as_stack_widget_parenting_children(self) -> None:
        renderer = QtRenderer()
        renderer.mount(build(Stack(children=[Text(content="a"), Text(content="b")])))
        widget = renderer.root_widget
        assert isinstance(widget, _StackWidget)
        assert len(renderer._at(()).children) == 2

    def test_absolute_child_fills_the_stack(self) -> None:
        renderer = QtRenderer()
        host = renderer.mount(
            build(
                Stack(
                    children=[
                        Text(
                            content="scrim",
                            style=Style(
                                position=Position.ABSOLUTE,
                                top=0,
                                left=0,
                                right=0,
                                bottom=0,
                            ),
                        )
                    ]
                )
            )
        )
        # Show + size the host so Qt delivers the resize down to the stack: a
        # never-shown widget never receives a resizeEvent.
        host.resize(200, 120)
        host.show()
        QApplication.processEvents()
        child = renderer._at((0,)).widget
        assert child.geometry().getRect() == (0, 0, 200, 120)

    def test_stack_align_centers_a_sized_child(self) -> None:
        renderer = QtRenderer()
        host = renderer.mount(
            build(
                Stack(
                    style=Style(stack_align=StackAlign.CENTER),
                    children=[Text(content="card", style=Style(width=40, height=20))],
                )
            )
        )
        host.resize(200, 100)
        host.show()
        QApplication.processEvents()
        assert renderer._at((0,)).widget.geometry().getRect() == (80, 40, 40, 20)

    def test_insert_and_reorder_keep_layers_in_sync(self) -> None:
        renderer = QtRenderer()
        first = Stack(children=[Text(content="a")])
        old = build(first)
        renderer.mount(old)
        new = build(Stack(children=[Text(content="a"), Text(content="b")]))
        renderer.apply(diff(old, new))
        assert len(renderer._at(()).children) == 2
        # Keyed reorder swaps z-order without rebuilding.
        keyed_old = build(
            Stack(children=[Text(key="a", content="a"), Text(key="b", content="b")])
        )
        renderer.remount(keyed_old)
        keyed_new = build(
            Stack(children=[Text(key="b", content="b"), Text(key="a", content="a")])
        )
        patches = diff(keyed_old, keyed_new)
        renderer.apply(patches)
        assert [c.props["content"] for c in renderer._at(()).children] == ["b", "a"]


# --- Qt renderer: gestures --------------------------------------------------


def _press(widget: _GestureWidget, x: float, y: float) -> None:
    widget.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _release(widget: _GestureWidget, x: float, y: float) -> None:
    widget.mouseReleaseEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


@pytest.mark.usefixtures("qapp")
class TestQtGestures:
    def _mount(self, **handlers: object) -> _GestureWidget:
        renderer = QtRenderer()
        renderer.mount(build(GestureDetector(child=Text(content="x"), **handlers)))  # type: ignore[arg-type]
        widget = renderer.root_widget
        assert isinstance(widget, _GestureWidget)
        return widget

    def test_short_press_release_is_a_tap(self) -> None:
        seen: list[TapEvent] = []
        widget = self._mount(on_tap=lambda e: seen.append(e))
        _press(widget, 5, 5)
        _release(widget, 7, 6)
        assert len(seen) == 1 and isinstance(seen[0], TapEvent)

    def test_long_horizontal_drag_is_a_right_swipe(self) -> None:
        seen: list[SwipeEvent] = []
        widget = self._mount(on_swipe=lambda e: seen.append(e))
        _press(widget, 5, 5)
        _release(widget, 120, 8)
        assert len(seen) == 1
        assert seen[0].direction is SwipeDirection.RIGHT
        assert seen[0].dx == pytest.approx(115.0)

    def test_long_press_timer_emits_long_press(self) -> None:
        seen: list[LongPressEvent] = []
        widget = self._mount(on_long_press=lambda e: seen.append(e))
        _press(widget, 5, 5)
        widget._fire_long_press()
        # A release after the long-press fired must not also emit a tap.
        _release(widget, 6, 6)
        assert len(seen) == 1 and isinstance(seen[0], LongPressEvent)

    def test_double_click_emits_double_tap(self) -> None:
        seen: list[TapEvent] = []
        widget = self._mount(on_double_tap=lambda e: seen.append(e))
        widget.mouseDoubleClickEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonDblClick,
                QPointF(3, 3),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        assert len(seen) == 1
