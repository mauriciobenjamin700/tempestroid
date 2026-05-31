"""Tests for the Tier 1 + Tier 2 CSS-style additions: opacity, shadow, gradients,
per-corner radius, per-side borders, and the richer typography/sizing knobs —
across the model, both ``Style`` translators, and the Qt renderer's effects.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tempestroid import (
    AlignItems,
    Border,
    Color,
    Corners,
    FontStyle,
    Gradient,
    GradientDirection,
    GradientStop,
    Shadow,
    SideBorder,
    Style,
    TextDecoration,
    TextOverflow,
    to_compose,
)
from tempestroid.renderers.qt.style_translator import self_alignment, to_qss

# --- model validation -------------------------------------------------------


def test_opacity_bounds() -> None:
    Style(opacity=0.0)
    Style(opacity=1.0)
    with pytest.raises(ValidationError):
        Style(opacity=1.5)
    with pytest.raises(ValidationError):
        Style(opacity=-0.1)


def test_gradient_requires_a_stop() -> None:
    Gradient(stops=[GradientStop(color=Color(r=0, g=0, b=0), position=0.0)])
    with pytest.raises(ValidationError):
        Gradient(stops=[])


def test_gradient_stop_position_bounds() -> None:
    with pytest.raises(ValidationError):
        GradientStop(color=Color(r=0, g=0, b=0), position=1.5)


def test_max_lines_and_aspect_ratio_positive() -> None:
    Style(max_lines=1, aspect_ratio=0.1)
    with pytest.raises(ValidationError):
        Style(max_lines=0)
    with pytest.raises(ValidationError):
        Style(aspect_ratio=0.0)


def test_new_value_models_are_frozen() -> None:
    shadow = Shadow(blur=4.0)
    with pytest.raises(ValidationError):
        shadow.blur = 8.0  # type: ignore[misc]


# --- Style → Compose --------------------------------------------------------


def test_compose_gradient_background() -> None:
    spec = to_compose(
        Style(
            background=Gradient(
                direction=GradientDirection.LEFT_RIGHT,
                stops=[
                    GradientStop(color=Color(r=255, g=0, b=0), position=0.0),
                    GradientStop(color=Color(r=0, g=0, b=255), position=1.0),
                ],
            )
        )
    )
    assert spec["background"]["kind"] == "gradient"
    assert spec["background"]["direction"] == "leftRight"
    assert spec["background"]["stops"][0] == {"color": "#ff0000", "position": 0.0}


def test_compose_corners_and_side_border() -> None:
    spec = to_compose(
        Style(
            radius=Corners(top_left=12, top_right=12),
            border=SideBorder(bottom=Border(width=1, color=Color(r=0, g=0, b=0))),
        )
    )
    assert spec["radius"] == {
        "topLeft": 12.0,
        "topRight": 12.0,
        "bottomRight": 0.0,
        "bottomLeft": 0.0,
    }
    assert spec["border"]["bottom"] == {"width": 1.0, "color": "#000000"}
    assert spec["border"]["top"] is None


def test_compose_effects_and_typography() -> None:
    spec = to_compose(
        Style(
            opacity=0.5,
            shadow=Shadow(color=Color(r=0, g=0, b=0), blur=4, offset_y=2),
            font_style=FontStyle.ITALIC,
            text_decoration=TextDecoration.LINE_THROUGH,
            letter_spacing=1.5,
            line_height=1.4,
            max_lines=2,
            text_overflow=TextOverflow.ELLIPSIS,
            align_self=AlignItems.CENTER,
            aspect_ratio=1.5,
        )
    )
    assert spec["opacity"] == 0.5
    assert spec["shadow"] == {
        "color": "#000000",
        "blur": 4.0,
        "offsetX": 0.0,
        "offsetY": 2.0,
    }
    assert spec["fontStyle"] == "italic"
    assert spec["textDecoration"] == "lineThrough"
    assert spec["letterSpacing"] == 1.5
    assert spec["lineHeight"] == 1.4
    assert spec["maxLines"] == 2
    assert spec["textOverflow"] == "ellipsis"
    assert spec["alignSelf"] == "center"
    assert spec["aspectRatio"] == 1.5


# --- Style → Qt (QSS) -------------------------------------------------------


def test_qss_gradient_background() -> None:
    qss = to_qss(
        Style(
            background=Gradient(
                stops=[
                    GradientStop(color=Color(r=0, g=0, b=0), position=0.0),
                    GradientStop(color=Color(r=255, g=255, b=255), position=1.0),
                ]
            )
        ),
        with_padding=True,
    )
    assert "qlineargradient(x1:0, y1:0, x2:0, y2:1" in qss


def test_qss_per_corner_radius_and_side_border() -> None:
    qss = to_qss(
        Style(
            radius=Corners(top_left=8),
            border=SideBorder(bottom=Border(width=2, color=Color(r=1, g=2, b=3))),
        ),
        with_padding=False,
    )
    assert "border-top-left-radius: 8.0px" in qss
    assert "border-bottom: 2.0px solid rgba(1, 2, 3, 1.0)" in qss
    assert "border-top:" not in qss


def test_qss_font_style_and_decoration() -> None:
    qss = to_qss(
        Style(font_style=FontStyle.ITALIC, text_decoration=TextDecoration.UNDERLINE),
        with_padding=True,
    )
    assert "font-style: italic" in qss
    assert "text-decoration: underline" in qss


def test_qss_ignores_renderer_level_effects() -> None:
    """opacity/shadow/letter_spacing are renderer-applied, never in QSS."""
    qss = to_qss(
        Style(opacity=0.3, shadow=Shadow(blur=4), letter_spacing=2.0),
        with_padding=True,
    )
    assert qss == ""


# --- self_alignment helper --------------------------------------------------


def test_self_alignment_maps_cross_axis() -> None:
    from PySide6.QtCore import Qt

    row = self_alignment(is_row=True, align_self=AlignItems.CENTER)
    col = self_alignment(is_row=False, align_self=AlignItems.START)
    assert row == Qt.AlignmentFlag.AlignVCenter
    assert col == Qt.AlignmentFlag.AlignLeft
    assert self_alignment(is_row=True, align_self=None) is None
    # STRETCH has no single-flag equivalent.
    assert self_alignment(is_row=True, align_self=AlignItems.STRETCH) is None
