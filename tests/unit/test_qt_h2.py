"""Qt-renderer H2 design-system tests (field / selection / slider / IconButton).

These pin the desktop simulator's half of the Trilho H phase-H2 contract: the
input-family (Input/TextArea/Dropdown/…), the selection family (Checkbox/Switch),
the slider family (Slider/RangeSlider) and the new ``IconButton`` consume the
engine-resolved styles + per-state variant tables rather than re-deriving any
variant logic.

- A field's resting box (OUTLINE all-sides border, FILLED background, FLUSHED
  bottom-only ``SideBorder``) is the engine-baked ``style``; the renderer paints
  the ``:focus`` / ``:hover`` / ``:disabled`` M3 paint deltas on top
  (``resolve_field_variant_states``). An ``error`` bakes the invalid (error-role)
  border into both the resting box and the states.
- A selection's accent fill (checked) / ring (unchecked) / box dim come from
  ``resolve_selection_variant_states`` and map onto the ``::indicator``
  sub-control; the >=48dp touch target stays on the row.
- A slider's active track + thumb (``color``) and inactive track (``background``)
  come from ``resolve_slider_variant_states`` and map onto ``::sub-page`` /
  ``::add-page`` / handle.
- An ``IconButton`` renders a glyph-only square ``QPushButton`` reusing the
  ``Variant``-based ``Button`` state-layer pass.
- The Material-alias gap is closed by delegating to the engine's
  ``MATERIAL_ALIASES`` (no Qt-local duplication).

All run headless under ``QT_QPA_PLATFORM=offscreen`` (see ``tests/conftest.py``).
"""

# These tests reach into the renderer's private helpers/widgets by design.
# pyright: reportPrivateUsage=false
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QSlider
from tempest_core import (
    resolve_field_variant_states,
    resolve_selection_variant_states,
    resolve_slider_variant_states,
)
from tempest_core.style import Border, Color, ComponentState, FieldVariant, Size
from tempest_core.theme import Theme
from tempest_core.widgets import (
    Checkbox,
    IconButton,
    Input,
    RangeSlider,
    Slider,
    Switch,
)

from tempestroid import build
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import (
    _icon_pixmap,
    _RangeSliderWidget,
    _resolve_icon_name,
)
from tempestroid.renderers.qt.style_translator import state_layer_qss

pytestmark = pytest.mark.usefixtures("qapp")


def _blocks(stylesheet: str) -> dict[str, str]:
    """Parse a scoped multi-block stylesheet into ``{selector_suffix: body}``.

    The base block keys under ``""``; pseudo/sub-control blocks key under the
    text after ``#name`` (e.g. ``":focus"``, ``"::indicator"``,
    ``"::indicator:hover"``).
    """
    blocks: dict[str, str] = {}
    for line in stylesheet.splitlines():
        line = line.strip()
        if not line or "{" not in line:
            continue
        selector, body = line.split("{", 1)
        body = body.rsplit("}", 1)[0].strip()
        suffix = selector.strip()
        # Drop the leading ``#name`` so the suffix is just the state/sub-control.
        if suffix.startswith("#"):
            suffix = suffix[1:]
            # The object name is the leading run of name chars before ':' / '::'.
            idx = suffix.find(":")
            suffix = suffix[idx:] if idx != -1 else ""
        blocks[suffix] = body
    return blocks


def _line_edit(renderer: QtRenderer) -> QLineEdit:
    """Return the single ``QLineEdit`` in a renderer's mounted host."""
    widget = renderer.host.findChild(QLineEdit)
    assert isinstance(widget, QLineEdit)
    return widget


# --- fields ----------------------------------------------------------------


def test_outline_field_emits_focus_hover_disabled_blocks() -> None:
    """An OUTLINE input paints :focus / :hover / :disabled state-layer blocks."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.OUTLINE)))
    blocks = _blocks(_line_edit(renderer).styleSheet())
    states = resolve_field_variant_states(
        variant=FieldVariant.OUTLINE,
        size=Size.MD,
        color_scheme="primary",
        theme=Theme(),
    )
    for suffix in (":focus", ":hover", ":disabled"):
        assert suffix in blocks, f"missing {suffix} block"
    assert blocks[":focus"] == state_layer_qss(states[ComponentState.FOCUS])
    assert blocks[":hover"] == state_layer_qss(states[ComponentState.HOVER])
    assert blocks[":disabled"] == state_layer_qss(states[ComponentState.DISABLED])


def test_focus_block_has_two_px_role_border() -> None:
    """The field focus state adds a 2px role-colored border."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.OUTLINE)))
    focus = _blocks(_line_edit(renderer).styleSheet())[":focus"]
    assert "border: 2.0px solid" in focus


def test_invalid_field_uses_error_role_border() -> None:
    """An ``error`` bakes the error-role border into the resting box + states."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.OUTLINE, error="Required")))
    blocks = _blocks(_line_edit(renderer).styleSheet())
    states = resolve_field_variant_states(
        variant=FieldVariant.OUTLINE,
        size=Size.MD,
        color_scheme="primary",
        theme=Theme(),
        invalid=True,
    )

    error_border = states[ComponentState.DEFAULT].border
    assert isinstance(error_border, Border) and error_border.color is not None
    error_rgba = error_border.color.to_rgba_string()
    # The resting box paints the error border, and the focus block keeps it.
    assert error_rgba in blocks[""]
    assert error_rgba in blocks[":focus"]


def test_filled_field_resting_box_has_background_no_border() -> None:
    """A FILLED input's resting box carries a fill and no resting border."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.FILLED)))
    base = _blocks(_line_edit(renderer).styleSheet())[""]
    assert "background-color:" in base
    assert "border:" not in base  # no all-sides resting border for FILLED


def test_flushed_field_resting_box_is_bottom_border_only() -> None:
    """A FLUSHED input's resting box is a bottom-only side border, radius 0."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.FLUSHED)))
    base = _blocks(_line_edit(renderer).styleSheet())[""]
    assert "border-bottom:" in base
    assert "border-radius: 0" in base
    # No all-sides ``border:`` shorthand (that would be OUTLINE).
    assert "border:" not in base


def test_field_disabled_block_fades_to_38_percent() -> None:
    """The field disabled state fades content/border toward 38% alpha."""
    renderer = QtRenderer()
    renderer.mount(build(Input(field_variant=FieldVariant.OUTLINE)))
    disabled = _blocks(_line_edit(renderer).styleSheet())[":disabled"]
    assert ", 0.38)" in disabled


# --- selection -------------------------------------------------------------


def test_checked_checkbox_indicator_has_accent_fill() -> None:
    """A checked checkbox paints the accent background onto its ``::indicator``."""
    renderer = QtRenderer()
    renderer.mount(build(Checkbox(checked=True)))
    cb = renderer.host.findChild(QCheckBox)
    assert isinstance(cb, QCheckBox)
    blocks = _blocks(cb.styleSheet())
    assert "::indicator" in blocks
    indicator = blocks["::indicator"]
    states = resolve_selection_variant_states(
        size=Size.MD, color_scheme="primary", theme=Theme(), checked=True
    )

    bg = states[ComponentState.DEFAULT].background
    assert isinstance(bg, Color)
    assert f"background-color: {bg.to_rgba_string()}" in indicator
    # Box dimension is pinned on the indicator, not the row.
    assert "width:" in indicator and "height:" in indicator


def test_unchecked_checkbox_indicator_has_ring_border() -> None:
    """An unchecked checkbox paints the ring border (no fill) on its indicator."""
    renderer = QtRenderer()
    renderer.mount(build(Checkbox(checked=False)))
    cb = renderer.host.findChild(QCheckBox)
    assert isinstance(cb, QCheckBox)
    indicator = _blocks(cb.styleSheet())["::indicator"]
    assert "border:" in indicator
    assert "background-color" not in indicator  # no fill when unchecked


def test_switch_keeps_48dp_touch_target_on_row() -> None:
    """A Switch keeps the >=48dp touch target on the row, not the box."""
    renderer = QtRenderer()
    renderer.mount(build(Switch(checked=True)))
    cb = renderer.host.findChild(QCheckBox)
    assert isinstance(cb, QCheckBox)
    blocks = _blocks(cb.styleSheet())
    # The base (row) block pins the touch target; the indicator carries the box.
    assert "min-height: 48.0px" in blocks[""]


def test_selection_indicator_hover_block_emitted() -> None:
    """A selection emits a ``::indicator:hover`` state-layer block."""
    renderer = QtRenderer()
    renderer.mount(build(Checkbox(checked=False)))
    cb = renderer.host.findChild(QCheckBox)
    assert isinstance(cb, QCheckBox)
    blocks = _blocks(cb.styleSheet())
    assert "::indicator:hover" in blocks


# --- slider ----------------------------------------------------------------


def test_slider_track_uses_resolved_active_and_inactive() -> None:
    """A slider paints the resolved active (sub-page) + inactive (add-page) track."""
    renderer = QtRenderer()
    renderer.mount(build(Slider(value=50)))
    sl = renderer.host.findChild(QSlider)
    assert isinstance(sl, QSlider)
    blocks = _blocks(sl.styleSheet())
    states = resolve_slider_variant_states(
        size=Size.MD, color_scheme="primary", theme=Theme()
    )

    default = states[ComponentState.DEFAULT]
    assert default.color is not None and default.background is not None
    active = default.color.to_rgba_string()
    assert "::sub-page:horizontal" in blocks
    assert active in blocks["::sub-page:horizontal"]
    assert "::add-page:horizontal" in blocks
    assert "::handle:horizontal" in blocks


def test_range_slider_styles_both_handles() -> None:
    """A range slider paints the resolved track onto both backing handles."""
    renderer = QtRenderer()
    renderer.mount(build(RangeSlider(low=20.0, high=80.0)))
    widget = renderer.host.findChild(_RangeSliderWidget)
    assert isinstance(widget, _RangeSliderWidget)
    low, high = widget.sliders()
    for slider in (low, high):
        blocks = _blocks(slider.styleSheet())
        assert "::sub-page:horizontal" in blocks
        assert "::add-page:horizontal" in blocks


# --- IconButton ------------------------------------------------------------


def test_icon_button_renders_glyph_no_text() -> None:
    """An IconButton renders a non-null icon and no text, with an a11y name."""
    renderer = QtRenderer()
    renderer.mount(build(IconButton(icon="photo_camera", label="Take photo")))
    btn = renderer.host.findChild(QPushButton)
    assert isinstance(btn, QPushButton)
    # QtSvg present in CI: the alias resolves to a glyph; guard if it is missing.
    if _icon_pixmap("photo_camera", 20, QColor(0, 0, 0)) is not None:
        assert not btn.icon().isNull()
        assert btn.text() == ""
    assert btn.accessibleName() == "Take photo"


def test_icon_button_geometry_is_square() -> None:
    """An IconButton's baked style is a 48x48 square with a circular radius."""
    button = IconButton(icon="settings", label="Settings")
    assert button.style is not None
    assert button.style.width == button.style.height == 48.0
    assert button.style.radius == 24.0  # circular (half the side)


def test_icon_button_renders_as_a_fixed_square() -> None:
    """The mounted IconButton widget is pinned to a true square (not ovalled).

    Regression guard: the resolved style carries the inherited text-button
    ``padding`` + ``min_height``, which a QPushButton turns into a QSS
    ``min-height = content + padding`` larger than the ``setFixedHeight`` square —
    so without stripping them (and re-pinning ``setFixedSize``) the disc renders
    taller than it is wide. Assert the widget's fixed min == max == 48 on BOTH
    axes (this checks the rendered widget, not just the baked style).
    """
    renderer = QtRenderer()
    renderer.mount(build(IconButton(icon="settings", label="Settings")))
    btn = renderer.host.findChild(QPushButton)
    assert isinstance(btn, QPushButton)
    assert btn.minimumWidth() == btn.maximumWidth() == 48
    assert btn.minimumHeight() == btn.maximumHeight() == 48


def test_icon_button_reuses_button_state_layers() -> None:
    """An IconButton carries the Variant-based M3 :hover/:pressed state blocks."""
    renderer = QtRenderer()
    renderer.mount(build(IconButton(icon="settings", label="Settings")))
    btn = renderer.host.findChild(QPushButton)
    assert isinstance(btn, QPushButton)
    blocks = _blocks(btn.styleSheet())
    assert ":hover" in blocks
    assert ":pressed" in blocks
    assert ":focus" in blocks
    assert ":disabled" in blocks


def test_icon_button_unknown_glyph_falls_back_to_text() -> None:
    """An unknown icon name shows the name as text (no crash, never invisible)."""
    renderer = QtRenderer()
    renderer.mount(
        build(IconButton(icon="totally_unknown_glyph_xyz", label="Mystery"))
    )
    btn = renderer.host.findChild(QPushButton)
    assert isinstance(btn, QPushButton)
    assert btn.text() == "totally_unknown_glyph_xyz"


# --- icon alias gap closed (engine-delegated) ------------------------------


def test_icon_alias_resolution_delegates_to_engine() -> None:
    """``_resolve_icon_name`` maps Material aliases via the engine's table."""
    assert _resolve_icon_name("photo_camera") == "eye"
    assert _resolve_icon_name("history") == "clock"
    assert _resolve_icon_name("person") == "user"
    # A curated/unknown name passes through unchanged.
    assert _resolve_icon_name("search") == "search"
    assert _resolve_icon_name("nope_nope") == "nope_nope"


def test_photo_camera_resolves_to_glyph() -> None:
    """``Icon(name="photo_camera")`` still resolves to a glyph pixmap."""
    pixmap = _icon_pixmap("photo_camera", 24, QColor(0, 0, 0))
    if pixmap is not None:  # guard if QtSvg is unavailable
        assert not pixmap.isNull()
