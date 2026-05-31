from PySide6.QtCore import Qt

from tempestroid import (
    AlignItems,
    Border,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    Style,
)
from tempestroid.renderers.qt import layout_alignment, to_qss


def test_to_qss_none_is_empty():
    assert to_qss(None, with_padding=True) == ""


def test_to_qss_paint_and_typography():
    style = Style(
        background=Color.from_hex("#102030"),
        color=Color.from_hex("#ffffff"),
        radius=8.0,
        font_size=14.0,
        font_weight=FontWeight.BOLD,
    )
    qss = to_qss(style, with_padding=True)
    assert "background-color: rgba(16, 32, 48, 1.0)" in qss
    assert "color: rgba(255, 255, 255, 1.0)" in qss
    assert "border-radius: 8.0px" in qss
    assert "font-size: 14.0px" in qss
    assert "font-weight: 700" in qss


def test_to_qss_border():
    style = Style(border=Border(width=2.0, color=Color.from_hex("#000000")))
    assert "border: 2.0px solid rgba(0, 0, 0, 1.0)" in to_qss(style, with_padding=True)


def test_to_qss_padding_only_when_requested():
    style = Style(padding=Edge.all(4.0))
    assert "padding: 4.0px 4.0px 4.0px 4.0px" in to_qss(style, with_padding=True)
    assert "padding" not in to_qss(style, with_padding=False)


def test_layout_alignment_row_center():
    flag = layout_alignment(
        is_row=True, justify=JustifyContent.CENTER, align=AlignItems.CENTER
    )
    assert flag is not None
    assert flag & Qt.AlignmentFlag.AlignHCenter
    assert flag & Qt.AlignmentFlag.AlignVCenter


def test_layout_alignment_column_main_is_vertical():
    flag = layout_alignment(
        is_row=False, justify=JustifyContent.END, align=AlignItems.START
    )
    assert flag is not None
    assert flag & Qt.AlignmentFlag.AlignBottom  # main axis (vertical) end
    assert flag & Qt.AlignmentFlag.AlignLeft  # cross axis (horizontal) start


def test_layout_alignment_unmapped_returns_none():
    # SPACE_BETWEEN + STRETCH have no single-flag mapping in v1.
    assert (
        layout_alignment(
            is_row=True,
            justify=JustifyContent.SPACE_BETWEEN,
            align=AlignItems.STRETCH,
        )
        is None
    )
