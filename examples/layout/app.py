"""Refined-layout demo — Wrap chips, a paginated PageView, and a CollapsingAppBar
that shrinks as the content scrolls (device-ready, E6).

Showcases the phase-E6 widgets:

- :class:`~tempestroid.Wrap` — a flow-layout of chips that wrap to the next line
  when the row fills (``Style.flex_wrap``).
- :class:`~tempestroid.PageView` — a paginated horizontal carousel; the active
  page lives in app state and a :class:`~tempestroid.PageChangeEvent` updates it,
  rendered with a simple dot indicator.
- :class:`~tempestroid.CollapsingAppBar` — a sliver-style header whose height
  eases down as the simulated scroll offset grows.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/layout/app.py

Or on a device via code-push::

    uv run tempest serve examples/layout/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    AspectRatio,
    Button,
    CollapsingAppBar,
    Color,
    Column,
    Container,
    Edge,
    FlexWrap,
    PageChangeEvent,
    PageView,
    Row,
    Style,
    Text,
    Widget,
    Wrap,
)

_CHIPS = (
    "Python",
    "Kotlin",
    "Compose",
    "Qt",
    "Pydantic",
    "asyncio",
    "JNI",
    "Gradle",
    "Reconciler",
    "Widgets",
)
_PAGES = ("Overview", "Details", "Settings")


@dataclass
class LayoutState:
    """The demo's mutable state.

    Attributes:
        page: The active carousel page index.
        scroll_offset: The simulated scroll offset driving the collapsing bar.
    """

    page: int = 0
    scroll_offset: float = 0.0


def make_state() -> LayoutState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new layout-demo state.
    """
    return LayoutState()


def _chip(label: str) -> Widget:
    """Build a single rounded chip.

    Args:
        label: The chip's text.

    Returns:
        A padded, rounded ``Container`` wrapping the label.
    """
    return Container(
        key=f"chip-{label}",
        style=Style(
            padding=Edge.symmetric(vertical=6.0, horizontal=12.0),
            radius=14.0,
            background=Color.from_hex("#2563eb"),
        ),
        child=Text(content=label, style=Style(color=Color.from_hex("#ffffff"))),
    )


def _dot(active: bool) -> Widget:
    """Build a page-indicator dot.

    Args:
        active: Whether the dot marks the active page.

    Returns:
        A small fixed-size rounded ``Container``.
    """
    return Container(
        style=Style(
            width=10.0,
            height=10.0,
            radius=5.0,
            background=Color.from_hex("#f9fafb" if active else "#374151"),
        ),
    )


def view(app: App[LayoutState]) -> Widget:
    """Build the refined-layout UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the layout demo.
    """
    state = app.state

    def on_page_change(event: PageChangeEvent) -> None:
        if event.page == state.page:
            return  # guard against a feedback loop

        def settle(s: LayoutState) -> None:
            s.page = event.page

        app.set_state(settle)

    def scroll_by(delta: float) -> None:
        def move(s: LayoutState) -> None:
            s.scroll_offset = max(0.0, s.scroll_offset + delta)

        app.set_state(move)

    page = AspectRatio(
        ratio=16 / 9,
        child=Container(
            style=Style(background=Color.from_hex("#111827"), padding=Edge.all(20.0)),
            child=Text(
                content=f"Page: {_PAGES[state.page]}",
                style=Style(font_size=22.0, color=Color.from_hex("#f9fafb")),
            ),
        ),
    )

    indicator = Row(
        style=Style(gap=8.0),
        children=[_dot(i == state.page) for i in range(len(_PAGES))],
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            CollapsingAppBar(
                title="Refined Layout",
                expanded_height=180.0,
                collapsed_height=64.0,
                scroll_offset=state.scroll_offset,
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(label="Scroll down", on_click=lambda: scroll_by(40.0)),
                    Button(label="Scroll up", on_click=lambda: scroll_by(-40.0)),
                ],
            ),
            Text(content="Chips (Wrap)", style=Style(font_size=18.0)),
            Wrap(
                style=Style(flex_wrap=FlexWrap.WRAP, gap=8.0),
                children=[_chip(label) for label in _CHIPS],
            ),
            Text(content="Carousel (PageView)", style=Style(font_size=18.0)),
            PageView(
                page=state.page,
                on_page_change=on_page_change,
                children=[page],
            ),
            indicator,
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(
                        label="Prev",
                        on_click=lambda: on_page_change(
                            PageChangeEvent(
                                page=max(0, state.page - 1), previous=state.page
                            )
                        ),
                    ),
                    Button(
                        label="Next",
                        on_click=lambda: on_page_change(
                            PageChangeEvent(
                                page=min(len(_PAGES) - 1, state.page + 1),
                                previous=state.page,
                            )
                        ),
                    ),
                ],
            ),
        ],
    )


def main() -> int:
    """Run the refined-layout demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — layout", size=(390, 760))


if __name__ == "__main__":
    raise SystemExit(main())
