from tempestroid import (
    AlignItems,
    Border,
    Color,
    Edge,
    FlexDirection,
    FontWeight,
    JustifyContent,
    Style,
    TextAlign,
    to_compose,
)


def test_none_style_is_empty():
    assert to_compose(None) == {}


def test_unset_fields_are_omitted():
    assert to_compose(Style()) == {}


def test_flex_mapping():
    spec = to_compose(
        Style(
            direction=FlexDirection.COLUMN,
            justify=JustifyContent.SPACE_BETWEEN,
            align=AlignItems.CENTER,
            grow=1.0,
            gap=8.0,
        )
    )
    assert spec["arrangement"] == "spaceBetween"
    assert spec["alignment"] == "center"
    assert spec["weight"] == 1.0
    assert spec["gap"] == 8.0


def test_box_and_paint_mapping():
    spec = to_compose(
        Style(
            padding=Edge.all(4.0),
            background=Color.from_hex("#101418"),
            color=Color.from_hex("#ffffff"),
            border=Border(width=2.0, color=Color.from_hex("#000000")),
            radius=8.0,
        )
    )
    assert spec["padding"] == {"top": 4.0, "right": 4.0, "bottom": 4.0, "left": 4.0}
    assert spec["background"] == "#101418"
    assert spec["color"] == "#ffffff"
    assert spec["border"] == {"width": 2.0, "color": "#000000"}
    assert spec["radius"] == 8.0


def test_typography_and_dimensions():
    spec = to_compose(
        Style(
            font_family="Inter",
            font_size=14.0,
            font_weight=FontWeight.BOLD,
            text_align=TextAlign.CENTER,
            width=120.0,
            max_height=40.0,
        )
    )
    assert spec["fontFamily"] == "Inter"
    assert spec["fontSize"] == 14.0
    assert spec["fontWeight"] == 700
    assert spec["textAlign"] == "center"
    assert spec["width"] == 120.0
    assert spec["maxHeight"] == 40.0


def test_spec_is_json_serializable():
    import json

    spec = to_compose(Style(background=Color.from_hex("#abc"), gap=2.0))
    json.dumps(spec)  # must not raise
