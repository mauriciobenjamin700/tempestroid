"""Qt renderer tests for the previously-deferred style fields now wired into the
simulator: fixed ``width``/``height``/``aspect_ratio``, ``text_align`` and the
text-flow trio (``max_lines``/``text_overflow``/``line_height``) on the custom
text label, and ``SPACE_*`` ``justify`` distribution via stretch spacers. Runs
headless via the offscreen platform from ``tests/conftest.py``.

Assertions stay on the public surface (``QtRenderer`` + the Qt widget tree) so
the tests pin observable behaviour, not renderer internals.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLayout

from tempestroid import (
    Column,
    JustifyContent,
    Row,
    Style,
    Text,
    TextAlign,
    TextOverflow,
    build,
    diff,
)
from tempestroid.renderers.qt import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")

#: ``QWIDGETSIZE_MAX`` — Qt's "no maximum" size, restored when a fixed dimension
#: is cleared.
_QT_SIZE_MAX = 16_777_215


# --- fixed dimensions -------------------------------------------------------


def test_fixed_width_and_height_pin_the_widget() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(width=120, height=48))))
    widget = renderer.root_widget
    assert widget.minimumWidth() == 120
    assert widget.maximumWidth() == 120
    assert widget.minimumHeight() == 48
    assert widget.maximumHeight() == 48


def test_aspect_ratio_derives_height_from_fixed_width() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(width=120, aspect_ratio=1.5))))
    widget = renderer.root_widget
    assert widget.maximumWidth() == 120
    # height = width / ratio = 120 / 1.5 = 80
    assert widget.maximumHeight() == 80


def test_aspect_ratio_derives_width_from_fixed_height() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(height=60, aspect_ratio=2.0))))
    widget = renderer.root_widget
    assert widget.maximumHeight() == 60
    # width = height * ratio = 60 * 2.0 = 120
    assert widget.maximumWidth() == 120


def test_sizing_reset_to_flexible_on_update() -> None:
    renderer = QtRenderer()
    old = build(Text(content="x", style=Style(width=120, height=48)))
    renderer.mount(old)
    new = build(Text(content="x", style=Style()))
    renderer.apply(diff(old, new))
    widget = renderer.root_widget
    assert widget.minimumWidth() == 0
    assert widget.maximumWidth() == _QT_SIZE_MAX
    assert widget.maximumHeight() == _QT_SIZE_MAX


# --- text alignment ---------------------------------------------------------


def _label(renderer: QtRenderer) -> QLabel:
    """Return the rooted ``QLabel`` (Text widgets back onto a label)."""
    widget = renderer.root_widget
    assert isinstance(widget, QLabel)
    return widget


def test_text_align_sets_label_alignment() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(text_align=TextAlign.RIGHT))))
    assert bool(_label(renderer).alignment() & Qt.AlignmentFlag.AlignRight)


def test_text_align_defaults_to_left() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style())))
    assert bool(_label(renderer).alignment() & Qt.AlignmentFlag.AlignLeft)


# --- text flow (max_lines / text_overflow / line_height) --------------------


def test_max_lines_enables_word_wrap() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="long text", style=Style(max_lines=2))))
    assert _label(renderer).wordWrap()


def test_plain_text_keeps_word_wrap_off() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Text(content="x", style=Style(font_size=14.0))))
    assert not _label(renderer).wordWrap()


def test_text_flow_painting_does_not_raise() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Text(
                content="a rather long sentence that must wrap and clip",
                style=Style(
                    max_lines=1,
                    text_overflow=TextOverflow.ELLIPSIS,
                    line_height=1.4,
                    width=80,
                    height=40,
                ),
            )
        )
    )
    label = _label(renderer)
    # Force a paint pass to exercise the custom QTextLayout path off-screen.
    label.resize(80, 40)
    label.grab()


# --- SPACE_* distribution ---------------------------------------------------


def _layout(renderer: QtRenderer) -> QLayout:
    layout = renderer.root_widget.layout()
    assert layout is not None
    return layout


def _spacer_count(renderer: QtRenderer) -> int:
    layout = _layout(renderer)
    count = 0
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is not None and item.spacerItem() is not None:
            count += 1
    return count


def _label_texts(renderer: QtRenderer) -> list[str]:
    """Read the text of each non-spacer label in the root layout, in order."""
    layout = _layout(renderer)
    texts: list[str] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if isinstance(widget, QLabel):
            texts.append(widget.text())
    return texts


def test_space_between_inserts_inter_item_spacers() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Row(
                style=Style(justify=JustifyContent.SPACE_BETWEEN),
                children=[Text(content="a"), Text(content="b"), Text(content="c")],
            )
        )
    )
    # 3 children → 2 spacers between them, none at the ends.
    assert _spacer_count(renderer) == 2


def test_space_evenly_inserts_end_spacers_too() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Row(
                style=Style(justify=JustifyContent.SPACE_EVENLY),
                children=[Text(content="a"), Text(content="b")],
            )
        )
    )
    # 2 children → spacers at both ends + 1 between = 3.
    assert _spacer_count(renderer) == 3


def test_space_around_inserts_end_spacers() -> None:
    renderer = QtRenderer()
    renderer.mount(
        build(
            Row(
                style=Style(justify=JustifyContent.SPACE_AROUND),
                children=[Text(content="a"), Text(content="b")],
            )
        )
    )
    assert _spacer_count(renderer) == 3


def test_justify_change_strips_stale_spacers() -> None:
    renderer = QtRenderer()
    old = build(
        Row(
            style=Style(justify=JustifyContent.SPACE_BETWEEN),
            children=[Text(content="a"), Text(content="b")],
        )
    )
    renderer.mount(old)
    assert _spacer_count(renderer) == 1
    new = build(
        Row(
            style=Style(justify=JustifyContent.CENTER),
            children=[Text(content="a"), Text(content="b")],
        )
    )
    renderer.apply(diff(old, new))
    assert _spacer_count(renderer) == 0


def test_insert_keeps_child_order_with_spacers() -> None:
    renderer = QtRenderer()
    old = build(
        Column(
            style=Style(justify=JustifyContent.SPACE_BETWEEN),
            children=[Text(content="a"), Text(content="c")],
        )
    )
    renderer.mount(old)
    new = build(
        Column(
            style=Style(justify=JustifyContent.SPACE_BETWEEN),
            children=[Text(content="a"), Text(content="b"), Text(content="c")],
        )
    )
    renderer.apply(diff(old, new))
    # 3 children now → 2 spacers, children still in source order.
    assert _spacer_count(renderer) == 2
    assert _label_texts(renderer) == ["a", "b", "c"]
