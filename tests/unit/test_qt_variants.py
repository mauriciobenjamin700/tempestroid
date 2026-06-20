"""Qt-renderer Chakra-variant + Material 3 state-layer tests (Trilho H, H1).

These pin the desktop simulator's half of the H1 design-system contract:

- A styled :class:`~tempest_core.widgets.Button` renders the engine-resolved base
  QSS (background / foreground / border / padding / radius) for each
  ``variant`` / ``size`` / ``color_scheme`` combination.
- The button's scoped stylesheet additionally carries ``:hover`` / ``:pressed`` /
  ``:focus`` / ``:disabled`` pseudo-state blocks whose colors are the Material 3
  state layers the engine's ``resolve_variant_states`` computes — so the simulator
  shows the same state feedback Compose paints with native ``InteractionSource``
  layers.

The resolution stays pure and in ``tempest_core``; the renderer only maps the
per-state styles onto Qt QSS pseudo-states. All run headless under
``QT_QPA_PLATFORM=offscreen`` (see ``tests/conftest.py``).
"""

# These tests reach into the renderer's private helpers/widgets by design.
# pyright: reportPrivateUsage=false
import pytest
from PySide6.QtWidgets import QPushButton
from tempest_core import resolve_variant_states
from tempest_core.style import (
    Border,
    Color,
    ComponentState,
    Edge,
    Size,
    Style,
    Variant,
)
from tempest_core.theme import Theme, ThemeMode

from tempestroid import App, Button, Column, build
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.style_translator import state_layer_qss

pytestmark = pytest.mark.usefixtures("qapp")


def _button_widget(renderer: QtRenderer) -> QPushButton:
    """Return the single ``QPushButton`` in a renderer's mounted host."""
    button = renderer.host.findChild(QPushButton)
    assert isinstance(button, QPushButton)
    return button


def _blocks(stylesheet: str) -> dict[str, str]:
    """Parse a scoped multi-block stylesheet into ``{selector_suffix: body}``.

    The renderer emits ``#name { … }`` for the base and ``#name:state { … }`` for
    each pseudo-state. This keys each block by its state suffix (``""`` for the
    base block, ``"hover"`` / ``"pressed"`` / ``"focus"`` / ``"disabled"``).
    """
    blocks: dict[str, str] = {}
    for line in stylesheet.splitlines():
        line = line.strip()
        if not line or "{" not in line:
            continue
        selector, body = line.split("{", 1)
        body = body.rsplit("}", 1)[0].strip()
        suffix = selector.split(":", 1)[1].strip() if ":" in selector else ""
        blocks[suffix] = body
    return blocks


# --- base style per variant ------------------------------------------------


def test_solid_button_base_qss_carries_resolved_colors() -> None:
    """A solid/primary button paints the resolved role bg + on-role fg + padding."""
    renderer = QtRenderer()
    renderer.mount(
        build(Button(label="Go", variant=Variant.SOLID, color_scheme="primary"))
    )
    base = _blocks(_button_widget(renderer).styleSheet())[""]
    default = resolve_variant_states(
        variant=Variant.SOLID, size=Size.MD, color_scheme="primary", theme=Theme()
    )[ComponentState.DEFAULT]
    assert isinstance(default.background, Color)
    assert f"background-color: {default.background.to_rgba_string()}" in base
    assert default.color is not None
    assert f"color: {default.color.to_rgba_string()}" in base
    assert "min-height: 48.0px" in base  # touch target preserved


def test_outline_button_base_qss_has_role_border() -> None:
    """An outline button paints a 1px role-colored border + role-colored content."""
    renderer = QtRenderer()
    renderer.mount(
        build(Button(label="Go", variant=Variant.OUTLINE, color_scheme="secondary"))
    )
    base = _blocks(_button_widget(renderer).styleSheet())[""]
    default = resolve_variant_states(
        variant=Variant.OUTLINE,
        size=Size.MD,
        color_scheme="secondary",
        theme=Theme(),
    )[ComponentState.DEFAULT]
    assert isinstance(default.border, Border) and default.border.color is not None
    assert f"border: 1.0px solid {default.border.color.to_rgba_string()}" in base


def test_link_button_base_qss_is_underlined() -> None:
    """A link button carries the underline text decoration in its base block."""
    renderer = QtRenderer()
    renderer.mount(
        build(Button(label="Go", variant=Variant.LINK, color_scheme="primary"))
    )
    base = _blocks(_button_widget(renderer).styleSheet())[""]
    assert "text-decoration: underline" in base


@pytest.mark.parametrize("size", [Size.XS, Size.SM, Size.MD, Size.LG])
def test_every_size_keeps_min_touch_target(size: Size) -> None:
    """Every density still pins the >=48dp M3 touch target in its base block."""
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Go", size=size, color_scheme="primary")))
    base = _blocks(_button_widget(renderer).styleSheet())[""]
    assert "min-height: 48.0px" in base


# --- state layers ----------------------------------------------------------


@pytest.mark.parametrize(
    "variant",
    [Variant.SOLID, Variant.OUTLINE, Variant.GHOST, Variant.LINK],
)
def test_state_layer_blocks_match_engine(variant: Variant) -> None:
    """Each pseudo-state block emits the engine-resolved M3 state-layer paint."""
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Go", variant=variant, color_scheme="primary")))
    blocks = _blocks(_button_widget(renderer).styleSheet())
    states = resolve_variant_states(
        variant=variant, size=Size.MD, color_scheme="primary", theme=Theme()
    )
    for state, suffix in (
        (ComponentState.HOVER, "hover"),
        (ComponentState.PRESSED, "pressed"),
        (ComponentState.FOCUS, "focus"),
        (ComponentState.DISABLED, "disabled"),
    ):
        assert suffix in blocks, f"missing :{suffix} block for {variant}"
        assert blocks[suffix] == state_layer_qss(states[state])


def test_hover_pressed_overlay_colors_differ_from_base() -> None:
    """Hover/pressed tint the background away from the resting color (M3 layer)."""
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Go", variant=Variant.SOLID)))
    blocks = _blocks(_button_widget(renderer).styleSheet())
    states = resolve_variant_states(
        variant=Variant.SOLID, size=Size.MD, color_scheme="primary", theme=Theme()
    )
    base_bg = states[ComponentState.DEFAULT].background
    hover_bg = states[ComponentState.HOVER].background
    assert base_bg != hover_bg  # the layer actually changes the color
    assert isinstance(hover_bg, Color)
    assert f"background-color: {hover_bg.to_rgba_string()}" in blocks["hover"]


def test_focus_block_has_two_px_role_border() -> None:
    """The focus state layer adds a 2px role-colored indicator border."""
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Go", variant=Variant.SOLID)))
    focus = _blocks(_button_widget(renderer).styleSheet())["focus"]
    assert "border: 2.0px solid" in focus


def test_disabled_block_fades_content_to_38_percent() -> None:
    """The disabled state layer fades the content color to 38% alpha."""
    renderer = QtRenderer()
    renderer.mount(build(Button(label="Go", variant=Variant.SOLID)))
    disabled = _blocks(_button_widget(renderer).styleSheet())["disabled"]
    assert ", 0.38)" in disabled  # rgba(..., 0.38) faded content


# --- theme threading -------------------------------------------------------


def test_state_layers_resolve_against_app_dark_theme() -> None:
    """A dark app theme yields dark-scheme state layers (theme threaded in)."""
    button = Button(label="Go", variant=Variant.SOLID, color_scheme="primary")

    def view(_app: App[int]) -> Column:
        return Column(children=[button])

    app: App[int] = App(
        0, view, apply_patches=lambda _p: None, theme=Theme(mode=ThemeMode.DARK)
    )
    renderer = QtRenderer()
    renderer.set_app(app)
    renderer.mount(app.start())
    blocks = _blocks(_button_widget(renderer).styleSheet())
    dark_states = resolve_variant_states(
        variant=Variant.SOLID,
        size=Size.MD,
        color_scheme="primary",
        theme=Theme(mode=ThemeMode.DARK),
    )
    assert blocks["hover"] == state_layer_qss(dark_states[ComponentState.HOVER])


# --- robustness ------------------------------------------------------------


def test_non_button_widget_unaffected() -> None:
    """The state-layer pass only runs for buttons (smoke: a column mounts clean)."""
    renderer = QtRenderer()
    host = renderer.mount(build(Column(children=[])))
    assert host is renderer.host


def test_state_layer_qss_emits_only_paint_delta() -> None:
    """``state_layer_qss`` renders only bg/color/border, never padding/radius."""
    style = Style(
        background=Color(r=1, g=2, b=3),
        color=Color(r=4, g=5, b=6),
        padding=Edge(top=8.0, right=8.0, bottom=8.0, left=8.0),
        radius=12.0,
    )
    body = state_layer_qss(style)
    assert "background-color" in body
    assert "color: rgba(4, 5, 6" in body
    assert "padding" not in body
    assert "radius" not in body
