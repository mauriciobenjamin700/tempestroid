"""Qt renderer tests for the renderer-applied style effects: opacity, shadow,
per-child ``align_self`` and ``letter_spacing`` — none of which go through QSS.
Runs headless via the offscreen platform from ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
)

from tempestroid import (
    AlignItems,
    Column,
    Row,
    Shadow,
    Style,
    Text,
    build,
)
from tempestroid.renderers.qt import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")


def test_opacity_applies_graphics_effect() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(opacity=0.4))))
    effect = renderer.root_widget.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == 0.4


def test_shadow_applies_drop_shadow_effect() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(Text(content="x", style=Style(shadow=Shadow(blur=6, offset_y=3))))
    )
    effect = renderer.root_widget.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    assert effect.blurRadius() == 6.0
    assert effect.yOffset() == 3.0


def test_shadow_wins_over_opacity_single_effect() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(Text(content="x", style=Style(opacity=0.5, shadow=Shadow(blur=4))))
    )
    assert isinstance(renderer.root_widget.graphicsEffect(), QGraphicsDropShadowEffect)


def test_effect_cleared_on_update() -> None:
    renderer = QtRenderer()
    from tempestroid import diff

    old = build(Text(content="x", style=Style(opacity=0.4)))
    renderer.mount(old)
    new = build(Text(content="x", style=Style()))
    renderer.apply(diff(old, new))
    assert renderer.root_widget.graphicsEffect() is None


def test_letter_spacing_sets_font_spacing() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(letter_spacing=3.0))))
    font = renderer.root_widget.font()
    assert font.letterSpacingType() == QFont.SpacingType.AbsoluteSpacing
    assert font.letterSpacing() == 3.0


def test_align_self_sets_child_alignment_in_column() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Column(
                children=[
                    Text(content="a", style=Style(align_self=AlignItems.CENTER)),
                ]
            )
        )
    )
    layout = renderer.root_widget.layout()
    assert layout is not None
    item = layout.itemAt(0)
    assert item is not None
    # Column cross axis is horizontal → CENTER maps to HCenter.
    assert bool(item.alignment() & Qt.AlignmentFlag.AlignHCenter)


def test_align_self_sets_child_alignment_in_row() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Row(
                children=[
                    Text(content="a", style=Style(align_self=AlignItems.START)),
                ]
            )
        )
    )
    layout = renderer.root_widget.layout()
    assert layout is not None
    item = layout.itemAt(0)
    assert item is not None
    # Row cross axis is vertical → START maps to Top.
    assert bool(item.alignment() & Qt.AlignmentFlag.AlignTop)
