"""H2 gallery — the Chakra-style input/selection/slider kit on both renderers.

Exercises the Trilho H phase H2 widgets, each with a couple of
``variant``/``size``/``color_scheme`` permutations, so the Compose device
renderer can be visually verified against the resolved ``Style`` the engine
bakes:

* :class:`~tempest_core.widgets.button.IconButton` in its three variants
  (solid / outline / ghost) — each renders a curated glyph and routes taps;
* :class:`~tempest_core.widgets.inputs.Input` in its three ``field_variant``s
  (outline / filled / flushed), with a focus-colored role border;
* :class:`~tempest_core.widgets.inputs.Checkbox` / ``Switch`` painted with the
  ``color_scheme`` accent;
* a :class:`~tempest_core.widgets.inputs.Slider` with a colored track;
* an :class:`~tempest_core.widgets.inputs.Icon` using a Material alias name
  (``photo_camera``) to confirm alias parity resolves a glyph (not raw text).

Validation/handlers run entirely in Python; both renderers receive an already
resolved tree, so the device leaf only reads the baked ``Style`` colors.

Runs in the Qt simulator::

    uv run python examples/h2gallery/app.py
    uv run tempest dev examples/h2gallery/app.py     # + hot restart on save

Exposes ``view(app) -> Widget`` and ``make_state() -> S`` for ``tempest dev``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import FieldVariant, IconButton, Variant

from tempestroid import (
    App,
    Checkbox,
    Color,
    Column,
    Edge,
    Icon,
    Input,
    Row,
    SlideEvent,
    Slider,
    Style,
    Switch,
    Text,
    TextChangeEvent,
    ToggleEvent,
    Widget,
)


@dataclass
class GalleryState:
    """Mutable state backing the H2 gallery.

    Attributes:
        name: The current text of the controlled inputs.
        agree: Whether the checkbox is checked.
        wifi: Whether the switch is on.
        volume: The current slider value in ``[0, 100]``.
        taps: How many times any icon button was tapped.
    """

    name: str = ""
    agree: bool = True
    wifi: bool = False
    volume: float = 40.0
    taps: int = 0


def make_state() -> GalleryState:
    """Build the initial gallery state.

    Returns:
        A fresh :class:`GalleryState`.
    """
    return GalleryState()


def _section(title: str, *children: Widget) -> Column:
    """Wrap labelled children in a spaced section.

    Args:
        title: The section heading.
        *children: The widgets to stack under the heading.

    Returns:
        A :class:`~tempestroid.Column` with a heading and the children.
    """
    return Column(
        style=Style(gap=8, padding=Edge.all(4)),
        children=[
            Text(
                content=title,
                style=Style(font_size=16, color=Color.from_hex("#444444")),
            ),
            *children,
        ],
    )


def view(app: App[GalleryState]) -> Column:
    """Build the H2 gallery tree.

    Args:
        app: The owning application (read ``app.state``, wire handlers).

    Returns:
        The root :class:`~tempestroid.Column` for the gallery screen.
    """
    state = app.state

    def bump() -> None:
        app.set_state(lambda s: setattr(s, "taps", s.taps + 1))

    def set_name(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "name", event.value))

    def set_agree(event: ToggleEvent) -> None:
        app.set_state(lambda s: setattr(s, "agree", event.checked))

    def set_wifi(event: ToggleEvent) -> None:
        app.set_state(lambda s: setattr(s, "wifi", event.checked))

    def set_volume(event: SlideEvent) -> None:
        app.set_state(lambda s: setattr(s, "volume", event.value))

    return Column(
        style=Style(gap=16, padding=Edge.all(16)),
        children=[
            Text(content=f"H2 gallery — taps: {state.taps}", style=Style(font_size=20)),
            _section(
                "IconButton (solid / outline / ghost)",
                Row(
                    style=Style(gap=12),
                    children=[
                        IconButton(
                            icon="heart",
                            variant=Variant.SOLID,
                            color_scheme="primary",
                            label="Like",
                            on_click=bump,
                        ),
                        IconButton(
                            icon="star",
                            variant=Variant.OUTLINE,
                            color_scheme="secondary",
                            label="Favorite",
                            on_click=bump,
                        ),
                        IconButton(
                            icon="settings",
                            variant=Variant.GHOST,
                            color_scheme="primary",
                            label="Settings",
                            on_click=bump,
                        ),
                    ],
                ),
            ),
            _section(
                "Input (outline / filled / flushed)",
                Input(
                    value=state.name,
                    placeholder="Outline (primary)",
                    field_variant=FieldVariant.OUTLINE,
                    color_scheme="primary",
                    on_change=set_name,
                ),
                Input(
                    value=state.name,
                    placeholder="Filled (secondary)",
                    field_variant=FieldVariant.FILLED,
                    color_scheme="secondary",
                    on_change=set_name,
                ),
                Input(
                    value=state.name,
                    placeholder="Flushed (error)",
                    field_variant=FieldVariant.FLUSHED,
                    color_scheme="error",
                    on_change=set_name,
                ),
            ),
            _section(
                "Selection + slider (accent color)",
                Checkbox(
                    checked=state.agree,
                    label="I agree (secondary)",
                    color_scheme="secondary",
                    on_change=set_agree,
                ),
                Switch(
                    checked=state.wifi,
                    label="Wi-Fi (tertiary)",
                    color_scheme="tertiary",
                    on_change=set_wifi,
                ),
                Slider(
                    value=state.volume,
                    min_value=0,
                    max_value=100,
                    color_scheme="primary",
                    on_change=set_volume,
                ),
            ),
            _section(
                "Icon alias parity",
                Row(
                    style=Style(gap=12),
                    children=[
                        Icon(name="photo_camera", size=28),
                        Text(content="photo_camera -> eye glyph"),
                    ],
                ),
            ),
        ],
    )


def main() -> None:
    """Run the gallery in the Qt simulator (lazy import keeps the file device-safe)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(make_state(), view, title="tempestroid — H2 gallery", size=(420, 760))


if __name__ == "__main__":
    main()
