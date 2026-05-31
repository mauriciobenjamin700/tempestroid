import json

from tempestroid import (
    Button,
    Checkbox,
    Color,
    Column,
    DatePicker,
    FilePicker,
    Input,
    Style,
    Text,
    build,
    serialize_node,
    serialize_patch,
)
from tempestroid.core.ir import Insert, Remove, Reorder, Replace, Update


def test_serialize_text_node():
    node = serialize_node(build(Text(content="hi", style=Style(gap=2.0))))
    assert node["type"] == "Text"
    assert node["props"]["content"] == "hi"
    assert node["props"]["style"] == {"gap": 2.0}
    assert node["children"] == []


def test_serialize_drops_none_props():
    node = serialize_node(build(Text(content="x")))  # style is None
    assert "style" not in node["props"]


def test_serialize_handler_becomes_token_with_event():
    node = serialize_node(build(Button(label="go", on_click=lambda: None)))
    handler = node["props"]["on_click"]
    assert handler == {"$handler": "root:on_click", "event": "TapEvent"}


def test_serialize_handler_token_uses_child_path():
    tree = build(
        Column(children=[Text(content="a"), Button(label="b", on_click=lambda: None)])
    )
    node = serialize_node(tree)
    handler = node["children"][1]["props"]["on_click"]
    assert handler["$handler"] == "1:on_click"


def test_serialize_input_carries_value_and_handler():
    node = serialize_node(
        build(Input(value="hi", placeholder="name", on_change=lambda value: None))
    )
    assert node["type"] == "Input"
    assert node["props"]["value"] == "hi"
    assert node["props"]["placeholder"] == "name"
    assert node["props"]["on_change"] == {
        "$handler": "root:on_change",
        "event": "TextChangeEvent",
    }


def test_serialize_checkbox_carries_checked():
    node = serialize_node(build(Checkbox(label="agree", checked=True)))
    assert node["props"]["checked"] is True
    assert node["props"]["label"] == "agree"


def test_serialize_datepicker_handler_event():
    node = serialize_node(
        build(DatePicker(value="2026-05-31", on_change=lambda v: None))
    )
    assert node["props"]["value"] == "2026-05-31"
    assert node["props"]["on_change"]["event"] == "DateChangeEvent"


def test_serialize_filepicker_handler_event():
    node = serialize_node(build(FilePicker(on_select=lambda uri: None)))
    assert node["props"]["on_select"]["event"] == "FileSelectEvent"


def test_serialize_input_tree_is_json_safe():
    tree = build(
        Column(
            children=[
                Input(value="a", on_change=lambda v: None),
                Checkbox(label="b", checked=False),
                DatePicker(value="2026-01-01"),
                FilePicker(on_select=lambda uri: None),
            ]
        )
    )
    json.dumps(serialize_node(tree))  # must not raise


def test_serialize_is_json_safe():
    tree = build(
        Column(
            style=Style(background=Color.from_hex("#101418")),
            children=[Text(content="a"), Button(label="b", on_click=lambda: None)],
        )
    )
    json.dumps(serialize_node(tree))  # must not raise


def test_serialize_patch_update():
    old = build(Text(content="a"))
    new = build(Text(content="b"))
    from tempestroid import diff

    patch = serialize_patch(diff(old, new)[0])
    assert patch == {"op": "update", "path": [], "set": {"content": "b"}, "unset": []}


def test_serialize_patch_insert_carries_node():
    out = serialize_patch(Insert(path=(), index=1, node=build(Text(content="new"))))
    assert out["op"] == "insert"
    assert out["index"] == 1
    assert out["node"]["props"]["content"] == "new"


def test_serialize_patch_remove_and_reorder():
    assert serialize_patch(Remove(path=(0,), index=2)) == {
        "op": "remove", "path": [0], "index": 2,
    }
    assert serialize_patch(Reorder(path=(), order=[1, 0])) == {
        "op": "reorder", "path": [], "order": [1, 0],
    }


def test_serialize_patch_replace():
    out = serialize_patch(Replace(path=(0,), node=build(Button(label="x"))))
    assert out["op"] == "replace"
    assert out["node"]["type"] == "Button"


def test_update_handler_set_prop_uses_path_token():
    # An Update carrying a handler (no node type) still emits a path token.
    out = serialize_patch(Update(path=(2,), set_props={"on_click": lambda: None}))
    assert out["set"]["on_click"]["$handler"] == "2:on_click"
