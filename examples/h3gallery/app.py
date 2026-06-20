"""H3 design-system gallery — the styled surface & layout kit.

Showcases the Trilho H phase H3 components: ``Card`` (elevated / filled /
outlined), ``Surface``, the stack helpers (``HStack`` / ``VStack`` / ``Spacer``),
``Divider`` and ``ListTile`` — each resolving its look from the design-system
``Theme`` (Material 3 tokens) via the ``CardVariant`` API, with no hand-set
colors.

Run in the Qt simulator::

    uv run python examples/h3gallery/app.py

The file stays renderer-agnostic — the Qt renderer is imported lazily inside
``main`` so the device loader (which has no PySide6) can import this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Avatar,
    Button,
    Card,
    CardVariant,
    Color,
    Column,
    Divider,
    Edge,
    FontWeight,
    HStack,
    ListTile,
    Spacer,
    Style,
    Surface,
    Text,
    VStack,
    Widget,
)


@dataclass
class GalleryState:
    """The showcase's mutable state.

    Attributes:
        taps: How many times the in-card action button was tapped.
    """

    taps: int = 0


def make_state() -> GalleryState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gallery state with the tap counter at zero.
    """
    return GalleryState()


def _heading(title: str, *, key: str) -> Widget:
    """Build a small uppercase section heading.

    Args:
        title: The heading text.
        key: The stable diff key.

    Returns:
        A muted, bold ``Text`` label.
    """
    return Text(
        content=title,
        style=Style(
            color=Color.from_hex("#6b7280"),
            font_size=12.0,
            font_weight=FontWeight.BOLD,
        ),
        key=key,
    )


def view(app: App[GalleryState]) -> Widget:
    """Build the H3 gallery tree.

    Args:
        app: The application whose state drives the showcase.

    Returns:
        The root widget for the current state.
    """
    taps = app.state.taps

    def _bump() -> None:
        """Increment the tap counter and request a rebuild."""
        app.set_state(lambda s: GalleryState(taps=s.taps + 1))

    # The three M3 card treatments, each resolved from the theme by variant.
    cards = HStack(
        gap="md",
        key="cards",
        children=[
            Card(
                variant=CardVariant.ELEVATED,
                key="elevated",
                children=[
                    Text(content="Elevated", style=Style(font_weight=FontWeight.BOLD)),
                    Text(content="surface + shadow"),
                ],
            ),
            Card(
                variant=CardVariant.FILLED,
                key="filled",
                children=[
                    Text(content="Filled", style=Style(font_weight=FontWeight.BOLD)),
                    Text(content="surface_variant"),
                ],
            ),
            Card(
                variant=CardVariant.OUTLINED,
                key="outlined",
                children=[
                    Text(content="Outlined", style=Style(font_weight=FontWeight.BOLD)),
                    Text(content="outline border"),
                ],
            ),
        ],
    )

    # A tinted (color_scheme) elevated card holding a ListTile + Divider + an
    # action row that uses Spacer to push the button to the trailing edge.
    panel = Card(
        variant=CardVariant.ELEVATED,
        color_scheme="primary",
        key="panel",
        children=[
            ListTile(
                title="Maria Silva",
                subtitle="maria@example.com",
                leading=Avatar(label="MS", key="av"),
                key="tile",
            ),
            Divider(key="div"),
            HStack(
                gap="sm",
                key="actions",
                children=[
                    Text(content=f"Taps: {taps}", key="count"),
                    Spacer(key="sp"),
                    Button(label="Tap", on_click=_bump, key="tap"),
                ],
            ),
        ],
    )

    # A bare Surface (the un-padded primitive Card builds on).
    surface = Surface(
        variant=CardVariant.FILLED,
        key="surface",
        child=Text(content="Surface (filled, no inner padding)", key="st"),
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        key="root",
        children=[
            VStack(
                gap="sm",
                key="cards-block",
                children=[_heading("CARDS", key="h-cards"), cards],
            ),
            VStack(
                gap="sm",
                key="panel-block",
                children=[
                    _heading("PANEL (tinted + ListTile + Divider)", key="h-panel"),
                    panel,
                ],
            ),
            VStack(
                gap="sm",
                key="surface-block",
                children=[_heading("SURFACE", key="h-surface"), surface],
            ),
        ],
    )


def main() -> None:
    """Run the gallery in the Qt simulator (lazy import keeps the module clean)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(view, make_state())


if __name__ == "__main__":
    main()
