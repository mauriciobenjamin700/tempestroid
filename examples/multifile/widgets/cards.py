"""A small widget factory imported by the entry module.

Proves multi-file imports work on device: the bundle ships this module and the
host puts the project root on ``sys.path`` so ``from widgets.cards import …``
resolves exactly as on the desktop.
"""

from __future__ import annotations

from collections.abc import Callable

from tempestroid import (
    AlignItems,
    Button,
    Color,
    Column,
    Edge,
    Style,
    Text,
    Widget,
)


def counter_card(count: int, on_increment: Callable[[], None]) -> Widget:
    """Build the counter card UI.

    Args:
        count: The current count to display.
        on_increment: Handler invoked when the button is tapped.

    Returns:
        The card widget tree.
    """
    return Column(
        style=Style(
            padding=Edge.all(24),
            gap=16,
            align_items=AlignItems.START,
            background=Color(r=18, g=18, b=24),
        ),
        children=[
            Text(
                content=f"multi-file count = {count}",
                style=Style(text_color=Color(r=240, g=240, b=255), font_size=26),
            ),
            Button(
                label="increment",
                on_click=on_increment,
                style=Style(
                    padding=Edge.symmetric(vertical=12, horizontal=20),
                    background=Color(r=40, g=90, b=240),
                    text_color=Color(r=255, g=255, b=255),
                    corner_radius=14,
                ),
            ),
        ],
    )
