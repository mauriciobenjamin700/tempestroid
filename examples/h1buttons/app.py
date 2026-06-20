"""H1 Button variant showcase (Trilho H, phase H1).

Renders the Chakra-style ``Button`` variant matrix (solid/outline/ghost/link) ×
a couple of sizes × the ``primary`` color scheme, plus a tap counter so the
device-verify can exercise the tap → ``dispatchEvent`` → handler → patch path.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/h1buttons/app.py

On the device the same ``view``/``make_state`` are loaded by the Compose host;
each variant maps to its Material3 affordance (filled / outlined / text), and
Material3 supplies the native press/hover/focus state layers over the resolved
``Style`` colors.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    Row,
    Size,
    Style,
    Text,
    Variant,
    Widget,
)


@dataclass
class ButtonsState:
    """The showcase's mutable state.

    Attributes:
        taps: How many times any showcase button has been tapped.
    """

    taps: int = 0


def make_state() -> ButtonsState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new state with zero taps.
    """
    return ButtonsState()


def view(app: App[ButtonsState]) -> Widget:
    """Build the variant showcase UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget: a header, the live tap count, and a row per variant.
    """

    def bump() -> None:
        """Increment the tap counter (the tap-path proof)."""
        app.set_state(lambda s: setattr(s, "taps", s.taps + 1))

    def variant_row(variant: Variant) -> Widget:
        """Build a row of one variant at md + lg sizes.

        Args:
            variant: The variant treatment to show.

        Returns:
            A labelled row with the md and lg button for this variant.
        """
        return Column(
            style=Style(gap=4.0),
            key=f"group:{variant.value}",
            children=[
                Text(
                    content=variant.value.upper(),
                    style=Style(
                        color=Color.from_hex("#6b7280"),
                        font_size=12.0,
                        font_weight=FontWeight.BOLD,
                    ),
                    key="label",
                ),
                Row(
                    style=Style(gap=12.0, align_items=AlignItems.CENTER),
                    key="row",
                    children=[
                        Button(
                            label=f"{variant.value} md",
                            on_click=bump,
                            variant=variant,
                            size=Size.MD,
                            color_scheme="primary",
                            key="md",
                        ),
                        Button(
                            label=f"{variant.value} lg",
                            on_click=bump,
                            variant=variant,
                            size=Size.LG,
                            color_scheme="primary",
                            key="lg",
                        ),
                    ],
                ),
            ],
        )

    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#ffffff"),
        ),
        children=[
            Text(
                content="H1 Button variants",
                style=Style(
                    color=Color.from_hex("#111827"),
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Text(
                content=f"taps: {app.state.taps}",
                style=Style(color=Color.from_hex("#2563eb"), font_size=16.0),
                key="taps",
            ),
            variant_row(Variant.SOLID),
            variant_row(Variant.OUTLINE),
            variant_row(Variant.GHOST),
            variant_row(Variant.LINK),
        ],
    )


def main() -> int:
    """Run the showcase in the Qt simulator.

    Returns:
        The process exit code.
    """
    # Import the Qt renderer lazily so this module stays renderer-agnostic: the
    # Android device loads ``view``/``make_state`` from this same file and has no
    # PySide6, so a top-level Qt import would crash the on-device load.
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — H1 buttons", size=(420, 520))


if __name__ == "__main__":
    raise SystemExit(main())
