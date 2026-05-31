"""Color picker + settings — gallery example.

Tapping a swatch updates a live preview's ``background``; the toggle rows flip
boolean settings that re-style the preview text. This showcases dynamic ``Style``
updates flowing through the diff on every tap.

Runs in the Qt simulator::

    uv run python examples/colorpicker/app.py

and on a device via code-push::

    uv run tempest serve examples/colorpicker/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)

_SWATCHES: tuple[str, ...] = (
    "#ef4444",
    "#f59e0b",
    "#22c55e",
    "#3b82f6",
    "#a855f7",
    "#ec4899",
)


@dataclass
class PickerState:
    """The picker's mutable state.

    Attributes:
        background: The selected preview background as a hex string.
        bold: Whether the preview label is bold.
        large: Whether the preview label is large.
    """

    background: str = "#3b82f6"
    bold: bool = True
    large: bool = True


def make_state() -> PickerState:
    """Build a fresh initial state.

    Returns:
        A new picker state.
    """
    return PickerState()


def _swatch(app: App[PickerState], hex_value: str) -> Widget:
    """Build one color swatch button."""
    selected = app.state.background == hex_value
    return Button(
        label="●" if selected else " ",
        on_click=lambda: app.set_state(lambda s: setattr(s, "background", hex_value)),
        key=f"sw-{hex_value}",
        style=Style(
            padding=Edge.symmetric(vertical=16.0, horizontal=20.0),
            radius=10.0,
            background=Color.from_hex(hex_value),
            color=Color.from_hex("#ffffff"),
            font_size=18.0,
        ),
    )


def _toggle_row(app: App[PickerState], label: str, attr: str, value: bool) -> Widget:
    """Build a label + toggle button row bound to a boolean attribute."""
    mark = "✓" if value else "○"
    background = Color.from_hex("#16a34a") if value else Color.from_hex("#1f2937")

    def _flip(s: PickerState) -> None:
        setattr(s, attr, not getattr(s, attr))

    return Row(
        style=Style(gap=12.0),
        children=[
            Button(
                label=f"{mark}  {label}",
                on_click=lambda: app.set_state(_flip),
                key=f"tg-{attr}",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
                    radius=8.0,
                    background=background,
                    color=Color.from_hex("#f9fafb"),
                ),
            ),
        ],
        key=f"row-{attr}",
    )


def view(app: App[PickerState]) -> Widget:
    """Build the picker UI for the current state.

    Args:
        app: The running app.

    Returns:
        The root widget of the picker screen.
    """
    state = app.state
    preview_weight = FontWeight.BOLD if state.bold else FontWeight.NORMAL
    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Column(
                style=Style(
                    padding=Edge.all(28.0),
                    radius=14.0,
                    background=Color.from_hex(state.background),
                ),
                children=[
                    Text(
                        content="Preview",
                        style=Style(
                            font_size=32.0 if state.large else 18.0,
                            font_weight=preview_weight,
                            color=Color.from_hex("#ffffff"),
                        ),
                        key="preview",
                    ),
                ],
                key="preview-box",
            ),
            Row(
                style=Style(gap=10.0),
                children=[_swatch(app, hex_value) for hex_value in _SWATCHES[:3]],
                key="swatches-1",
            ),
            Row(
                style=Style(gap=10.0),
                children=[_swatch(app, hex_value) for hex_value in _SWATCHES[3:]],
                key="swatches-2",
            ),
            _toggle_row(app, "Bold label", "bold", state.bold),
            _toggle_row(app, "Large label", "large", state.large),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — color picker", size=(360, 520))
    )
