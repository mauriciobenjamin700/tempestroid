import pytest
from pydantic import ValidationError

from tempestroid import (
    Button,
    Checkbox,
    Column,
    Container,
    DatePicker,
    FilePicker,
    Input,
    Row,
    Style,
    Text,
    Widget,
)


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


def test_input_widgets_are_leaves():
    assert Input(value="x").child_nodes() == []
    assert Checkbox(label="ok").child_nodes() == []
    assert DatePicker(value="2026-05-31").child_nodes() == []
    assert FilePicker().child_nodes() == []


def test_input_widget_type_tags():
    assert Input().widget_type == "Input"
    assert Checkbox().widget_type == "Checkbox"
    assert DatePicker().widget_type == "DatePicker"
    assert FilePicker().widget_type == "FilePicker"


def test_input_widgets_carry_values():
    assert Input(value="hi", placeholder="name").value == "hi"
    assert Checkbox(label="agree", checked=True).checked is True
    assert DatePicker(value="2026-05-31").value == "2026-05-31"
    assert FilePicker().label == "Choose file"


def test_input_handlers_can_be_sync_or_async():
    from tempestroid import TextChangeEvent

    async def changed(event: TextChangeEvent) -> None:
        return None

    Input(on_change=lambda value: None)
    Input(on_change=changed)
    Checkbox(on_change=lambda checked: None)
    DatePicker(on_change=lambda value: None)
    FilePicker(on_select=lambda uri: None)
