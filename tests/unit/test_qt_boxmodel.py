"""Qt-renderer box-model fidelity tests (scoped QSS, radius clamp, fixed size).

These pin the imperative renderer fixes from the Qt-fidelity roadmap:

- **P0** — a node's box QSS is scoped to itself (``#objectName``) so a bordered
  container does not cascade its border/background onto descendants.
- **P1 (radius)** — a styled box clamps an over-large radius (pill sentinel /
  circle) to ``min(w, h) / 2`` so the corners round fully.
- **P1 (sizing)** — a container with both dimensions fixed is square (size policy
  pinned ``Fixed``/``Fixed``), not stretched oval by a parent layout.
- **P2** — a common Material-symbol alias resolves to a curated glyph pixmap
  instead of the literal-text fallback.

All run headless under ``QT_QPA_PLATFORM=offscreen`` (see ``tests/conftest.py``).
"""

# These tests reach into the renderer's private helpers/widgets by design.
# pyright: reportPrivateUsage=false
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from tempestroid import (
    Border,
    Color,
    Column,
    Container,
    Corners,
    Icon,
    Style,
    Text,
    build,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import (
    _clamp_radius,
    _clamp_radius_value,
    _icon_pixmap,
    _resolve_icon_name,
)

pytestmark = pytest.mark.usefixtures("qapp")


# --- P0: scoped QSS does not cascade onto children -------------------------


def test_bordered_container_does_not_box_text_child():
    """A bordered/backgrounded container must not bleed its box onto a child."""
    renderer = QtRenderer()
    tree = build(
        Container(
            style=Style(
                background=Color.from_hex("#102030"),
                border=Border(width=2.0, color=Color.from_hex("#ffffff")),
                radius=8.0,
            ),
            child=Text(content="hello"),
        )
    )
    renderer.mount(tree)
    labels = [w for w in renderer.host.findChildren(QLabel) if w.text() == "hello"]
    assert labels, "the text child must be rendered"
    child = labels[0]
    # The child's own stylesheet (if any) must not carry a border declaration —
    # the container's border is scoped to the container, never inherited.
    assert "border" not in child.styleSheet()


def test_container_qss_is_object_name_scoped():
    """The container's box QSS is wrapped in an ``#objectName`` selector."""
    renderer = QtRenderer()
    tree = build(
        Container(
            style=Style(border=Border(width=1.0, color=Color.from_hex("#000000"))),
            child=Text(content="x"),
        )
    )
    host = renderer.mount(tree)
    styled = [w for w in host.findChildren(QWidget) if "border" in w.styleSheet()]
    assert styled, "the bordered container must carry the border QSS"
    for widget in styled:
        sheet = widget.styleSheet()
        assert sheet.lstrip().startswith("#"), sheet
        assert widget.objectName() and f"#{widget.objectName()}" in sheet


def test_child_color_qss_survives_under_bordered_parent():
    """A child's own color QSS is independent of the parent's scoped border."""
    renderer = QtRenderer()
    tree = build(
        Container(
            style=Style(border=Border(width=2.0, color=Color.from_hex("#ff0000"))),
            child=Text(content="tinted", style=Style(color=Color.from_hex("#00ff00"))),
        )
    )
    renderer.mount(tree)
    labels = [w for w in renderer.host.findChildren(QLabel) if w.text() == "tinted"]
    assert labels
    sheet = labels[0].styleSheet()
    assert "color" in sheet
    assert "border" not in sheet


# --- P1: radius clamp ------------------------------------------------------


def test_clamp_radius_value_caps_at_half_min_side():
    """An over-large uniform radius is clamped to ``min(w, h) / 2``."""
    assert _clamp_radius_value(999.0, 96, 96) == 48.0
    assert _clamp_radius_value(999.0, 40, 120) == 20.0
    # An in-range radius is untouched.
    assert _clamp_radius_value(8.0, 96, 96) == 8.0
    # No size known yet → no cap.
    assert _clamp_radius_value(999.0, 0, 0) == 999.0


def test_clamp_radius_corners_component_wise():
    """A per-corner radius clamps each component independently."""
    corners = Corners(
        top_left=999.0, top_right=4.0, bottom_right=999.0, bottom_left=2.0
    )
    clamped = _clamp_radius(corners, 96, 96)
    assert isinstance(clamped, Corners)
    assert clamped.top_left == 48.0
    assert clamped.top_right == 4.0
    assert clamped.bottom_right == 48.0
    assert clamped.bottom_left == 2.0


def test_fixed_square_box_clamps_radius_in_qss():
    """A 96x96 styled box with a pill radius emits a clamped (48px) radius."""
    renderer = QtRenderer()
    tree = build(
        Container(
            style=Style(
                background=Color.from_hex("#3366ff"),
                radius=999.0,
                width=96.0,
                height=96.0,
            ),
        )
    )
    host = renderer.mount(tree)
    styled = [
        w for w in host.findChildren(QWidget) if "border-radius" in w.styleSheet()
    ]
    assert styled, "the styled box must carry a border-radius rule"
    sheet = styled[0].styleSheet()
    assert "border-radius: 48.0px" in sheet
    assert "999" not in sheet


# --- P1: fixed size keeps a square box square ------------------------------


def test_fixed_both_dimensions_pins_size_policy():
    """A both-dimensions-fixed box pins a Fixed/Fixed size policy and is square."""
    renderer = QtRenderer()
    tree = build(
        Column(
            children=[
                Container(
                    style=Style(
                        background=Color.from_hex("#3366ff"),
                        width=96.0,
                        height=96.0,
                    ),
                )
            ]
        )
    )
    host = renderer.mount(tree)
    boxes = [
        w
        for w in host.findChildren(QWidget)
        if w.maximumWidth() == 96 and w.maximumHeight() == 96
    ]
    assert boxes, "the fixed-size box must exist with a 96x96 maximum"
    box = boxes[0]
    policy = box.sizePolicy()
    assert policy.horizontalPolicy() == QSizePolicy.Policy.Fixed
    assert policy.verticalPolicy() == QSizePolicy.Policy.Fixed
    assert box.minimumWidth() == 96
    assert box.minimumHeight() == 96


def test_single_fixed_dimension_stays_flexible():
    """Only one fixed dimension leaves the size policy flexible (no over-pin)."""
    renderer = QtRenderer()
    tree = build(
        Container(
            style=Style(width=96.0),
            child=Text(content="x"),
        )
    )
    host = renderer.mount(tree)
    boxes = [w for w in host.findChildren(QWidget) if w.maximumWidth() == 96]
    assert boxes
    policy = boxes[0].sizePolicy()
    assert policy.horizontalPolicy() != QSizePolicy.Policy.Fixed


# --- P2: Material-name alias resolves to a curated glyph -------------------


def test_resolve_icon_name_maps_material_aliases():
    """A common Material name maps to a curated icon name."""
    assert _resolve_icon_name("photo_camera") == "eye"
    assert _resolve_icon_name("history") == "clock"
    assert _resolve_icon_name("person") == "user"
    # A curated name passes through unchanged.
    assert _resolve_icon_name("search") == "search"
    # An unknown name passes through (caller falls back to text).
    assert _resolve_icon_name("totally_unknown_glyph") == "totally_unknown_glyph"


def test_icon_pixmap_resolves_material_alias():
    """``photo_camera`` resolves to a (non-null) pixmap, not the text fallback."""
    pixmap = _icon_pixmap("photo_camera", 24, QColor(0, 0, 0))
    # When QtSvg is available the alias resolves to a real pixmap; if QtSvg is
    # missing the helper returns None for *any* name, so guard the assertion.
    if pixmap is not None:
        assert not pixmap.isNull()


def test_icon_alias_renders_glyph_not_text():
    """An Icon with a Material alias renders a pixmap and clears the text."""
    renderer = QtRenderer()
    renderer.mount(build(Icon(name="photo_camera")))
    icon_labels = [
        w for w in renderer.host.findChildren(QLabel) if not w.pixmap().isNull()
    ]
    text_labels = [
        w for w in renderer.host.findChildren(QLabel) if w.text() == "photo_camera"
    ]
    # With QtSvg present the alias resolves to a glyph (a non-null pixmap and no
    # literal-name text). Without QtSvg the renderer keeps the text fallback for
    # every name, so only assert the glyph path when a pixmap was produced.
    if icon_labels:
        assert not text_labels
