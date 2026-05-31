import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from tempestroid import (
    Button,
    Column,
    Container,
    Row,
    Text,
    build,
    diff,
)
from tempestroid.renderers.qt import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")


def _labels(widget: QWidget) -> list[str]:
    """Collect the text of every QLabel under a widget, depth-first."""
    return [child.text() for child in widget.findChildren(QLabel)]


def _ordered_labels(container: QWidget) -> list[str]:
    """Return QLabel texts in visual (layout) order for a container widget."""
    layout = container.layout()
    assert layout is not None
    out: list[str] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        assert item is not None
        child = item.widget()
        if isinstance(child, QLabel):
            out.append(child.text())
    return out


def test_mount_builds_widget_tree():
    renderer = QtRenderer()
    host = renderer.mount(build(Column(children=[Text(content="hello")])))
    assert isinstance(host, QWidget)
    assert _labels(host) == ["hello"]


def test_mount_button_label():
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Tap me")))
    buttons = renderer.root_widget.findChildren(QPushButton)
    # the root itself is the button
    assert isinstance(renderer.root_widget, QPushButton)
    assert renderer.root_widget.text() == "Tap me"
    assert buttons == []


def test_update_changes_label_text():
    renderer = QtRenderer()
    old = build(Text(content="a"))
    renderer.mount(old)
    new = build(Text(content="b"))
    renderer.apply(diff(old, new))
    assert isinstance(renderer.root_widget, QLabel)
    assert renderer.root_widget.text() == "b"


def test_insert_adds_child_widget():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a")]))
    renderer.mount(old)
    new = build(Column(children=[Text(content="a"), Text(content="b")]))
    renderer.apply(diff(old, new))
    assert _ordered_labels(renderer.root_widget) == ["a", "b"]


def test_remove_drops_child_widget():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a"), Text(content="b")]))
    renderer.mount(old)
    new = build(Column(children=[Text(content="a")]))
    renderer.apply(diff(old, new))
    assert _ordered_labels(renderer.root_widget) == ["a"]


def test_replace_swaps_widget_type():
    renderer = QtRenderer()
    old = build(Column(children=[Text(content="a")]))
    renderer.mount(old)
    new = build(Column(children=[Button(label="a")]))
    renderer.apply(diff(old, new))
    assert renderer.root_widget.findChildren(QPushButton)
    assert _labels(renderer.root_widget) == []


def test_root_replace_swaps_root():
    renderer = QtRenderer()
    old = build(Text(content="a"))
    renderer.mount(old)
    new = build(Button(label="now a button"))
    renderer.apply(diff(old, new))
    assert isinstance(renderer.root_widget, QPushButton)
    assert renderer.root_widget.text() == "now a button"


def test_reorder_changes_visual_order():
    renderer = QtRenderer()
    old = build(
        Column(children=[Text(content="a", key="a"), Text(content="b", key="b")])
    )
    renderer.mount(old)
    new = build(
        Column(children=[Text(content="b", key="b"), Text(content="a", key="a")])
    )
    patches = diff(old, new)
    renderer.apply(patches)
    assert _ordered_labels(renderer.root_widget) == ["b", "a"]


def test_button_click_invokes_sync_handler():
    clicks: list[int] = []
    renderer = QtRenderer()
    renderer.mount(build(Button(label="x", on_click=lambda: clicks.append(1))))
    assert isinstance(renderer.root_widget, QPushButton)
    renderer.root_widget.click()
    assert clicks == [1]


def test_update_rebinds_handler():
    calls: list[str] = []
    renderer = QtRenderer()
    old = Button(label="x", on_click=lambda: calls.append("old"))
    renderer.mount(build(old))
    new = Button(label="x", on_click=lambda: calls.append("new"))
    renderer.apply(diff(build(old), build(new)))
    assert isinstance(renderer.root_widget, QPushButton)
    renderer.root_widget.click()
    assert calls == ["new"]


def test_nested_container_renders():
    renderer = QtRenderer()
    tree = build(
        Column(
            children=[
                Row(children=[Text(content="x"), Text(content="y")]),
                Container(child=Text(content="z")),
            ]
        )
    )
    renderer.mount(tree)
    assert _labels(renderer.root_widget) == ["x", "y", "z"]
