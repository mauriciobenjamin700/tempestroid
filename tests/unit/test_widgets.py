import pytest
from pydantic import ValidationError

from tempestroid import Button, Column, Container, Row, Style, Text, Widget


def test_widget_type_tag():
    assert Text(content="hi").widget_type == "Text"
    assert Column().widget_type == "Column"


def test_leaf_has_no_children():
    assert Text(content="x").child_nodes() == []
    assert Button(label="ok").child_nodes() == []


def test_column_exposes_children_in_order():
    col = Column(children=[Text(content="a"), Text(content="b")])
    kids = col.child_nodes()
    assert [k.widget_type for k in kids] == ["Text", "Text"]
    first = kids[0]
    assert isinstance(first, Text)
    assert first.content == "a"


def test_container_wraps_single_child():
    assert Container().child_nodes() == []
    box = Container(child=Text(content="x"))
    kids = box.child_nodes()
    assert len(kids) == 1
    inner = kids[0]
    assert isinstance(inner, Text)
    assert inner.content == "x"


def test_subclass_identity_preserved_in_tree():
    """Subclass instances must survive validation without losing fields."""
    tree = Column(children=[Button(label="press")])
    child = tree.children[0]
    assert isinstance(child, Button)
    assert child.label == "press"


def test_handler_can_be_sync_or_async():
    async def handler() -> None:
        return None

    Button(label="a", on_click=lambda: None)
    Button(label="b", on_click=handler)


def test_invalid_child_type_rejected():
    with pytest.raises(ValidationError):
        Column(children=["not a widget"])  # type: ignore[list-item]


def test_style_attached_to_widget():
    w: Widget = Row(style=Style(gap=8.0))
    assert w.style is not None
    assert w.style.gap == 8.0
