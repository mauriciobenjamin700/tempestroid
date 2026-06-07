import json
from typing import Any

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


def test_serialize_canvas_commands_are_json_safe():
    from tempestroid import (
        ArcTo,
        Canvas,
        Close,
        DrawOval,
        DrawRect,
        DrawText,
        FillCmd,
        LineTo,
        MoveTo,
        StrokeCmd,
    )

    canvas = Canvas(
        commands=[
            MoveTo(x=0.0, y=0.0),
            LineTo(x=10.0, y=10.0),
            ArcTo(x=0.0, y=0.0, width=20.0, height=20.0,
                  start_angle=0.0, sweep_angle=90.0),
            Close(),
            DrawRect(x=1.0, y=2.0, width=3.0, height=4.0),
            DrawOval(x=5.0, y=6.0, width=7.0, height=8.0),
            FillCmd(color=[1.0, 0.0, 0.0, 1.0]),
            StrokeCmd(color=[0.0, 0.0, 1.0, 1.0], width=2.0),
            DrawText(text="hi", x=1.0, y=2.0),
        ]
    )
    node = serialize_node(build(canvas))
    assert node["type"] == "Canvas"
    commands: list[Any] = node["props"]["commands"]
    assert isinstance(commands, list) and len(commands) == 9
    assert all(isinstance(cmd, dict) and "kind" in cmd for cmd in commands)
    # Round-trips through json with no custom encoder and no tuples.
    json.dumps(node)
    fill: dict[str, Any] = next(c for c in commands if c["kind"] == "fill")
    assert fill["color"] == [1.0, 0.0, 0.0, 1.0]


def test_serialize_lowers_semantics_to_dict():
    """`Semantics` lowers to a {label, role, hint} dict so it crosses the bridge.

    Regression: a bare Semantics model used to hit the drop-through and never
    reach the device, so accessibility labels (Compose `Modifier.semantics`)
    were absent in the a11y tree.
    """
    from tempestroid import Semantics

    node = serialize_node(
        build(Text(content="hi", semantics=Semantics(label="greeting", role="heading")))
    )
    assert node["props"]["semantics"] == {"label": "greeting", "role": "heading"}
    # Stays JSON-safe.
    json.dumps(node)


def test_serialize_semantics_omits_none_fields():
    """Only the set Semantics fields cross (exclude_none)."""
    from tempestroid import Semantics

    node = serialize_node(build(Text(content="x", semantics=Semantics(label="only"))))
    assert node["props"]["semantics"] == {"label": "only"}


def test_serialize_icon_inlines_curated_path():
    """A curated `Icon` name gains an `iconPath` carrying its SVG `d` string."""
    from tempestroid import Icon
    from tempestroid.icons import icon_path

    node = serialize_node(build(Icon(name="search")))
    assert node["type"] == "Icon"
    assert node["props"]["name"] == "search"
    assert node["props"]["iconPath"] == icon_path("search")
    json.dumps(node)


def test_serialize_icon_unknown_name_has_no_path():
    """An unknown icon name carries no `iconPath` (device falls back to text)."""
    from tempestroid import Icon

    node = serialize_node(build(Icon(name="totally-not-an-icon")))
    assert node["props"]["name"] == "totally-not-an-icon"
    assert "iconPath" not in node["props"]


def test_serialize_input_inlines_leading_and_trailing_icon_paths():
    """`Input` leading/trailing icon names resolve to `*Path` siblings."""
    from tempestroid.icons import Icons, icon_path

    node = serialize_node(
        build(
            Input(
                value="",
                placeholder="email",
                leading_icon=Icons.MAIL,
                trailing_icon=Icons.EYE,
            )
        )
    )
    assert node["props"]["leading_icon"] == "mail"
    assert node["props"]["trailing_icon"] == "eye"
    assert node["props"]["leadingIconPath"] == icon_path("mail")
    assert node["props"]["trailingIconPath"] == icon_path("eye")
    json.dumps(node)


def test_serialize_dropdown_and_autocomplete_icon_paths():
    """`Dropdown`/`Autocomplete` resolve curated icon names like `Input`."""
    from tempestroid import Autocomplete, Dropdown
    from tempestroid.icons import icon_path

    dropdown = serialize_node(
        build(Dropdown(options=["a", "b"], leading_icon="user"))
    )
    assert dropdown["props"]["leadingIconPath"] == icon_path("user")

    autocomplete = serialize_node(
        build(Autocomplete(value="", options=["x"], trailing_icon="search"))
    )
    assert autocomplete["props"]["trailingIconPath"] == icon_path("search")


def test_serialize_input_without_icons_has_no_path_props():
    """An icon-less input never grows `*Path` props."""
    node = serialize_node(build(Input(value="x", placeholder="p")))
    assert "leadingIconPath" not in node["props"]
    assert "trailingIconPath" not in node["props"]
