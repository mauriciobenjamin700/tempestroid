"""H4 design-system gallery — the styled data-display & feedback kit.

Showcases the Trilho H phase H4 components: ``Alert``/``Banner`` (status
variants), ``Badge``/``Chip``/``Tag`` (the badge family), ``Stat``,
``ProgressStepper``, and ``ProgressBar`` — each resolving its look from the
design-system ``Theme`` via the new status ``color_scheme``s
(``success``/``warning``/``info`` + ``error``) and the variant API, with no
hand-set colors.

Run in the Qt simulator::

    uv run python examples/h4gallery/app.py

Renderer-agnostic — the Qt renderer is imported lazily inside ``main`` so the
device loader (no PySide6) can import this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    Alert,
    AlertVariant,
    App,
    Badge,
    BadgeVariant,
    Banner,
    Chip,
    Color,
    Column,
    Edge,
    FontWeight,
    HStack,
    ProgressBar,
    ProgressStepper,
    Row,
    Stat,
    Style,
    Tag,
    Text,
    VStack,
    Widget,
)


@dataclass
class GalleryState:
    """The showcase's mutable state.

    Attributes:
        step: The active step index in the ``ProgressStepper`` demo.
    """

    step: int = 1


def make_state() -> GalleryState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gallery state with the stepper on the second step.
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


def _section(title: str, *, key: str, body: Widget) -> Widget:
    """Build a titled section block.

    Args:
        title: The section heading.
        key: The stable diff key.
        body: The section content.

    Returns:
        A ``VStack`` with the heading above the body.
    """
    return VStack(
        gap="sm",
        key=key,
        children=[_heading(title, key="h"), body],
    )


def view(app: App[GalleryState]) -> Widget:
    """Build the H4 gallery tree.

    Args:
        app: The application whose state drives the showcase.

    Returns:
        The root widget for the current state.
    """
    statuses = ["info", "success", "warning", "error"]

    alerts = Column(
        style=Style(gap=8.0),
        key="alerts",
        children=[
            Alert(
                title=scheme.capitalize(),
                body=f"A {scheme} alert, themed from the {scheme} color_scheme.",
                color_scheme=scheme,
                variant=AlertVariant.SUBTLE,
                key=scheme,
            )
            for scheme in statuses
        ],
    )

    badges = HStack(
        gap="sm",
        key="badges",
        children=[
            Badge(label="solid", color_scheme="success", variant=BadgeVariant.SOLID,
                  key="b-solid"),
            Badge(label="subtle", color_scheme="warning", variant=BadgeVariant.SUBTLE,
                  key="b-subtle"),
            Badge(label="outline", color_scheme="info", variant=BadgeVariant.OUTLINE,
                  key="b-outline"),
            Chip(label="Chip", color_scheme="primary", key="chip"),
            Tag(label="Tag", color_scheme="secondary", key="tag"),
        ],
    )

    stats = HStack(
        gap="md",
        key="stats",
        children=[
            Stat(label="Revenue", value="R$ 12.4k", delta="+8.2%", delta_up=True,
                 key="s1"),
            Stat(label="Churn", value="2.1%", delta="-0.4%", delta_up=False,
                 key="s2"),
        ],
    )

    stepper = ProgressStepper(
        steps=["Cart", "Address", "Payment", "Done"],
        current=app.state.step,
        color_scheme="primary",
        key="stepper",
    )

    progress = ProgressBar(value=0.6, color_scheme="success", key="pbar")

    banner = Banner(
        message="Saved to the cloud.",
        color_scheme="info",
        variant=AlertVariant.SOLID,
        key="banner",
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        key="root",
        children=[
            _section("ALERTS (status color_schemes)", key="sec-alerts", body=alerts),
            _section("BADGES / CHIP / TAG", key="sec-badges", body=badges),
            _section("STAT", key="sec-stats", body=stats),
            _section("PROGRESS STEPPER", key="sec-stepper", body=stepper),
            _section("PROGRESS BAR", key="sec-progress", body=progress),
            _section("BANNER", key="sec-banner", body=banner),
            Row(
                style=Style(gap=8.0),
                key="ctl",
                children=[
                    Chip(
                        label="Next step",
                        on_click=lambda: app.set_state(
                            lambda s: GalleryState(step=min(s.step + 1, 3))
                        ),
                        color_scheme="primary",
                        key="next",
                    ),
                ],
            ),
        ],
    )


def main() -> None:
    """Run the gallery in the Qt simulator (lazy import keeps the module clean)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(view, make_state())


if __name__ == "__main__":
    main()
