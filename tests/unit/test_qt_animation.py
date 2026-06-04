"""Smoke tests for the Qt renderer's E3 animation widgets.

Each test mounts an animation widget through :class:`QtRenderer` under the
offscreen Qt platform (set by ``tests/conftest.py``) and asserts it materializes
without raising, plus the relevant insert/remove patch path runs. The actual
motion (``QPropertyAnimation``/``QTimer``) is fire-and-forget — these guard that
the renderer builds and patches the widgets, not that pixels move.
"""

# The animation tests reach into the renderer's private widget classes to assert
# their backing type — internal by design.
# pyright: reportPrivateUsage=false
import pytest
from PySide6.QtWidgets import QLabel

from tempestroid import (
    Animated,
    AnimatedList,
    Color,
    Hero,
    Shimmer,
    Skeleton,
    Style,
    Text,
    build,
    diff,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import (
    _AnimatedListWidget,
    _ShimmerWidget,
    _SkeletonWidget,
)

pytestmark = pytest.mark.usefixtures("qapp")


def test_animated_mounts_child() -> None:
    """An ``Animated`` wrapper mounts its child without error."""
    renderer = QtRenderer()
    tree = Animated(
        child=Text(content="hi", key="t"),
        style_begin=Style(opacity=0.0),
        style_end=Style(opacity=1.0),
    )
    host = renderer.mount(build(tree))
    labels = host.findChildren(QLabel)
    assert any(label.text() == "hi" for label in labels)


def test_shimmer_mounts() -> None:
    """A ``Shimmer`` mounts as a shimmer widget wrapping its child."""
    renderer = QtRenderer()
    tree = Shimmer(
        child=Text(content="loading", key="t"),
        base_color=Color(r=200, g=200, b=200),
        highlight_color=Color(r=250, g=250, b=250),
        duration_ms=800,
    )
    renderer.mount(build(tree))
    assert isinstance(renderer.root_widget, _ShimmerWidget)


def test_skeleton_mounts() -> None:
    """A ``Skeleton`` mounts as a childless skeleton widget."""
    renderer = QtRenderer()
    tree = Skeleton(width=120.0, height=16.0, radius=8.0)
    renderer.mount(build(tree))
    widget = renderer.root_widget
    assert isinstance(widget, _SkeletonWidget)
    assert widget.maximumWidth() == 120


def test_hero_mounts_child() -> None:
    """A ``Hero`` mounts its child and stamps the shared-element tag."""
    renderer = QtRenderer()
    tree = Hero(hero_tag="avatar", child=Text(content="A", key="t"))
    renderer.mount(build(tree))
    assert renderer.root_widget.property("tempest_hero_tag") == "avatar"


def test_animated_list_mounts_and_inserts() -> None:
    """An ``AnimatedList`` mounts its children and animates an inserted item."""
    renderer = QtRenderer()
    first = AnimatedList(
        children=[Text(content="a", key="a")],
        enter_duration_ms=10,
        exit_duration_ms=10,
    )
    renderer.mount(build(first))
    assert isinstance(renderer.root_widget, _AnimatedListWidget)
    # Insert a second item: the diff produces an Insert the renderer animates in.
    second = AnimatedList(
        children=[Text(content="a", key="a"), Text(content="b", key="b")],
        enter_duration_ms=10,
        exit_duration_ms=10,
    )
    patches = diff(build(first), build(second))
    renderer.apply(patches)
    labels = renderer.root_widget.findChildren(QLabel)
    assert {label.text() for label in labels} >= {"a", "b"}


def test_animated_list_remove_runs() -> None:
    """Removing an ``AnimatedList`` item runs the exit path without error."""
    renderer = QtRenderer()
    first = AnimatedList(
        children=[Text(content="a", key="a"), Text(content="b", key="b")],
        exit_duration_ms=10,
    )
    renderer.mount(build(first))
    second = AnimatedList(children=[Text(content="a", key="a")], exit_duration_ms=10)
    patches = diff(build(first), build(second))
    # Must not raise; the leaving widget animates out then deletes itself.
    renderer.apply(patches)
