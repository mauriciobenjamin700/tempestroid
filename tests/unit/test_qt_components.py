"""Qt renderer smoke tests for the expanded component gallery.

Each new widget must mount into the expected Qt backing widget and reflect its
props; the secure ``Input`` masks its text and grows a reveal toggle. Runs fully
headless via the offscreen platform configured in ``tests/conftest.py``.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSlider,
)

from tempestroid import (
    Icon,
    Image,
    Input,
    ProgressBar,
    ScrollView,
    Slider,
    Spinner,
    Switch,
    Text,
    TextArea,
    build,
)
from tempestroid.renderers.qt import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")


def test_slider_mounts_with_range_and_value() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Slider(value=30.0, min_value=0.0, max_value=100.0)))
    slider = renderer.root_widget
    assert isinstance(slider, QSlider)
    assert slider.minimum() == 0
    assert slider.maximum() == 100
    assert slider.value() == 30


def test_switch_mounts_as_checkbox() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Switch(label="dark", checked=True)))
    box = renderer.root_widget
    assert isinstance(box, QCheckBox)
    assert box.isChecked() is True
    assert box.text() == "dark"


def test_textarea_mounts_with_value() -> None:
    renderer = QtRenderer()
    renderer.mount(build(TextArea(value="line", placeholder="notes")))
    edit = renderer.root_widget
    assert isinstance(edit, QPlainTextEdit)
    assert edit.toPlainText() == "line"
    assert edit.placeholderText() == "notes"


def test_progressbar_determinate_value() -> None:
    renderer = QtRenderer()
    renderer.mount(build(ProgressBar(value=0.25)))
    bar = renderer.root_widget
    assert isinstance(bar, QProgressBar)
    assert (bar.minimum(), bar.maximum()) == (0, 100)
    assert bar.value() == 25


def test_progressbar_indeterminate_is_busy() -> None:
    renderer = QtRenderer()
    renderer.mount(build(ProgressBar(indeterminate=True)))
    bar = renderer.root_widget
    assert isinstance(bar, QProgressBar)
    assert (bar.minimum(), bar.maximum()) == (0, 0)


def test_spinner_is_busy_progressbar() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Spinner()))
    bar = renderer.root_widget
    assert isinstance(bar, QProgressBar)
    assert (bar.minimum(), bar.maximum()) == (0, 0)


def test_secure_input_masks_and_grows_eye_toggle() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Input(value="hunter2", secure=True)))
    field = renderer.root_widget
    assert isinstance(field, QLineEdit)
    assert field.echoMode() == QLineEdit.EchoMode.Password
    assert len(field.actions()) == 1


def test_plain_input_has_no_eye_toggle() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Input(value="x")))
    field = renderer.root_widget
    assert isinstance(field, QLineEdit)
    assert field.echoMode() == QLineEdit.EchoMode.Normal
    assert field.actions() == []


def test_secure_input_eye_toggle_uses_a_vector_icon() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Input(value="hunter2", secure=True)))
    field = renderer.root_widget
    assert isinstance(field, QLineEdit)
    (toggle,) = field.actions()
    # The reveal toggle carries a stroked line glyph (not an empty/emoji icon).
    assert not toggle.icon().isNull()


def test_input_leading_and_trailing_icon_slots() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Input(value="x", leading_icon="search", trailing_icon="x")))
    field = renderer.root_widget
    assert isinstance(field, QLineEdit)
    # Two decorative in-field icon actions (no eye, not secure).
    assert len(field.actions()) == 2
    assert all(not a.icon().isNull() for a in field.actions())


def test_input_icon_slots_update_without_stacking() -> None:
    from tempestroid.core.reconciler import diff

    renderer = QtRenderer()
    first = build(Input(value="x", leading_icon="search"))
    renderer.mount(first)
    field = renderer.root_widget
    assert isinstance(field, QLineEdit)
    assert len(field.actions()) == 1
    # Changing the leading icon replaces, never stacks.
    second = build(Input(value="x", leading_icon="user"))
    renderer.apply(diff(first, second))
    assert len(field.actions()) == 1
    # Clearing it removes the slot.
    third = build(Input(value="x"))
    renderer.apply(diff(second, third))
    assert field.actions() == []


def test_image_falls_back_to_alt_text() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Image(src="https://example.com/x.png", alt="logo")))
    label = renderer.root_widget
    assert isinstance(label, QLabel)
    assert label.text() == "logo"


def test_icon_renders_vector_glyph_for_curated_name() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Icon(name="home")))
    label = renderer.root_widget
    assert isinstance(label, QLabel)
    # A curated name renders a stroked vector pixmap, not the raw name as text.
    assert label.text() == ""
    pixmap = label.pixmap()
    assert not pixmap.isNull()


def test_icon_falls_back_to_name_text_for_unknown() -> None:
    renderer = QtRenderer()
    renderer.mount(build(Icon(name="not-a-real-icon")))
    label = renderer.root_widget
    assert isinstance(label, QLabel)
    # An unknown name keeps the legacy text fallback (no exception, no glyph).
    assert label.text() == "not-a-real-icon"
    assert label.pixmap().isNull()


def test_scrollview_mounts_children_in_scroll_area() -> None:
    renderer = QtRenderer()
    renderer.mount(build(ScrollView(children=[Text(content="a"), Text(content="b")])))
    area = renderer.root_widget
    assert isinstance(area, QScrollArea)
    labels = [lbl.text() for lbl in area.findChildren(QLabel)]
    assert labels == ["a", "b"]
