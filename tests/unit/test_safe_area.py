"""Tests for the ``SafeArea`` widget and its renderer/serializer behaviour.

``SafeArea`` insets its child away from system intrusions (status bar, nav bar,
notch). The widget is renderer-agnostic; the Qt simulator stands in with fixed
approximate insets, and the bridge serializes the ``edges`` set as plain strings
for the device's Compose renderer (which uses the real ``WindowInsets``).
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QLayout, QWidget

from tempestroid import (
    Column,
    SafeArea,
    SafeAreaEdge,
    Style,
    Text,
    build,
    serialize_node,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.style import Edge


def _margins(widget: QWidget) -> tuple[int, int, int, int]:
    """Return a widget's layout content margins as ``(left, top, right, bottom)``.

    Args:
        widget: The container widget whose layout margins to read.

    Returns:
        The four margins in logical pixels.
    """
    layout = widget.layout()
    assert isinstance(layout, QLayout)
    m = layout.contentsMargins()
    return m.left(), m.top(), m.right(), m.bottom()


def test_safe_area_defaults_to_all_edges() -> None:
    """A bare ``SafeArea`` protects every edge."""
    area = SafeArea(child=Text(content="hi"))
    assert area.edges == [
        SafeAreaEdge.TOP,
        SafeAreaEdge.RIGHT,
        SafeAreaEdge.BOTTOM,
        SafeAreaEdge.LEFT,
    ]


def test_safe_area_child_nodes() -> None:
    """``child_nodes`` exposes the wrapped child (or nothing when empty)."""
    child = Text(content="hi")
    assert SafeArea(child=child).child_nodes() == [child]
    assert SafeArea().child_nodes() == []


def test_build_carries_edges_in_props() -> None:
    """``build`` lowers ``edges`` into the node props (not the child slot)."""
    node = build(SafeArea(child=Text(content="hi"), edges=[SafeAreaEdge.TOP]))
    assert node.type == "SafeArea"
    assert node.props["edges"] == [SafeAreaEdge.TOP]
    assert len(node.children) == 1


def test_serialize_edges_as_plain_strings() -> None:
    """Serialization yields JSON-safe edge strings the device can parse."""
    node = build(SafeArea(child=Text(content="hi"), edges=[SafeAreaEdge.TOP]))
    serialized = serialize_node(node)
    assert serialized["type"] == "SafeArea"
    assert serialized["props"]["edges"] == ["top"]
    assert len(serialized["children"]) == 1
    # The whole envelope must round-trip through JSON (the JNI transport does).
    assert json.loads(json.dumps(serialized))["props"]["edges"] == ["top"]


@pytest.mark.usefixtures("qapp")
class TestSafeAreaQtRenderer:
    """The Qt simulator reserves approximate insets on the container margins."""

    def test_default_insets_all_edges(self) -> None:
        renderer = QtRenderer()
        renderer.mount(build(SafeArea(child=Text(content="hi"))))
        box = renderer.root_widget
        assert isinstance(box, QWidget)
        # Simulator stand-in: top/bottom 24, sides flush.
        assert _margins(box) == (0, 24, 0, 24)

    def test_subset_of_edges(self) -> None:
        renderer = QtRenderer()
        renderer.mount(
            build(SafeArea(child=Text(content="hi"), edges=[SafeAreaEdge.TOP]))
        )
        assert _margins(renderer.root_widget) == (0, 24, 0, 0)

    def test_insets_add_to_padding(self) -> None:
        renderer = QtRenderer()
        renderer.mount(
            build(
                SafeArea(
                    style=Style(padding=Edge.all(10)),
                    child=Text(content="hi"),
                )
            )
        )
        # 10 padding on every side + 24 top/bottom inset.
        assert _margins(renderer.root_widget) == (10, 34, 10, 34)

    def test_no_edges_reserves_nothing(self) -> None:
        renderer = QtRenderer()
        renderer.mount(build(SafeArea(child=Text(content="hi"), edges=[])))
        assert _margins(renderer.root_widget) == (0, 0, 0, 0)

    def test_child_renders_inside(self) -> None:
        renderer = QtRenderer()
        renderer.mount(build(SafeArea(child=Column(children=[Text(content="inner")]))))
        layout = renderer.root_widget.layout()
        assert isinstance(layout, QLayout)
        assert layout.count() == 1
