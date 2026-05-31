import pytest
from pydantic import ValidationError

from tempestroid import (
    AlignItems,
    Border,
    Color,
    Edge,
    FlexDirection,
    FontWeight,
    Style,
)


def test_color_from_hex_short_and_long():
    assert Color.from_hex("#fff") == Color(r=255, g=255, b=255)
    assert Color.from_hex("ff8800") == Color(r=255, g=136, b=0)


def test_color_from_hex_with_alpha():
    c = Color.from_hex("#00000080")
    assert c.r == 0 and c.g == 0 and c.b == 0
    assert round(c.a, 2) == 0.5


def test_color_str_coercion_in_style():
    style = Style.model_validate({"background": "#112233"})
    assert style.background == Color(r=0x11, g=0x22, b=0x33)


def test_color_to_hex_roundtrip():
    assert Color.from_hex("#1a2b3c").to_hex() == "#1a2b3c"
    assert Color.rgba(0, 0, 0, 0.5).to_hex() == "#00000080"


def test_color_invalid_hex():
    with pytest.raises(ValueError):
        Color.from_hex("#xyz")


def test_color_channel_bounds():
    with pytest.raises(ValidationError):
        Color(r=300, g=0, b=0)


def test_edge_constructors():
    assert Edge.all(8.0) == Edge(top=8, right=8, bottom=8, left=8)
    assert Edge.symmetric(vertical=4.0, horizontal=2.0) == Edge(
        top=4, bottom=4, left=2, right=2
    )


def test_style_is_frozen():
    style = Style(gap=4.0)
    with pytest.raises(ValidationError):
        style.gap = 8.0  # type: ignore[misc]


def test_style_merge_overrides_only_set_fields():
    base = Style(gap=4.0, color=Color.from_hex("#000"), font_weight=FontWeight.NORMAL)
    over = Style(gap=12.0, align=AlignItems.CENTER)
    merged = base.merge(over)
    assert merged.gap == 12.0
    assert merged.align == AlignItems.CENTER
    assert merged.color == Color.from_hex("#000")
    assert merged.font_weight == FontWeight.NORMAL


def test_border_defaults():
    assert Border().width == 0.0
    assert Border().color is None


def test_flex_direction_enum_value():
    assert FlexDirection.ROW.value == "row"
