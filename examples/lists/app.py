"""Virtualized lists demo — LazyColumn (10k items) + pagination + pull-to-refresh
and a SectionList with sticky headers (device-ready, E1).

Showcases the phase-E1 widgets:

- :class:`~tempestroid.LazyColumn` — a virtualized list that materializes only
  the visible window from an ``item_builder``; scrolling 10k items stays smooth
  because the IR never holds more than the window.
- ``on_end_reached`` — fires near the bottom (``end_reached_threshold``) to grow
  the loaded count (infinite scroll).
- ``on_refresh`` — pull-to-refresh resets the list and toggles ``refreshing``.
- :class:`~tempestroid.SectionList` — sections with a sticky header each.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/lists/app.py

Or on a device via code-push::

    uv run tempest serve examples/lists/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    Color,
    Column,
    Edge,
    EndReachedEvent,
    LazyColumn,
    RefreshEvent,
    SectionHeader,
    SectionList,
    Style,
    Text,
    Widget,
)

_TOTAL = 10_000
_PAGE = 50


@dataclass
class ListsState:
    """The demo's mutable state.

    Attributes:
        loaded: How many of the ``_TOTAL`` items are currently paginated in.
        refreshing: Whether the pull-to-refresh spinner is active.
        generation: Bumped on refresh so item labels visibly change.
    """

    loaded: int = _PAGE
    refreshing: bool = False
    generation: int = 0


def make_state() -> ListsState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new lists state.
    """
    return ListsState()


def view(app: App[ListsState]) -> Widget:
    """Build the lists UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the lists screen.
    """
    state = app.state

    def on_end_reached(_event: EndReachedEvent) -> None:
        def grow(s: ListsState) -> None:
            s.loaded = min(_TOTAL, s.loaded + _PAGE)

        app.set_state(grow)

    def on_refresh(_event: RefreshEvent) -> None:
        def reset(s: ListsState) -> None:
            s.refreshing = False
            s.loaded = _PAGE
            s.generation += 1

        app.set_state(reset)

    def build_row(index: int) -> Widget:
        return Column(
            style=Style(padding=Edge.all(14.0)),
            children=[
                Text(content=f"Item {index}  (gen {state.generation})"),
            ],
        )

    def build_section_item(index: int) -> Widget:
        return Text(content=f"  row {index}", style=Style(padding=Edge.all(10.0)))

    def build_header(title: str) -> Widget:
        return Text(
            content=title,
            style=Style(
                padding=Edge.all(12.0),
                background=Color.from_hex("#101418"),
                color=Color.from_hex("#ffffff"),
                font_size=18.0,
            ),
        )

    sections = [
        SectionHeader(
            title=f"Section {letter}",
            item_count=20,
            item_builder=build_section_item,
            header_builder=lambda title=f"Section {letter}": build_header(title),
        )
        for letter in ("A", "B", "C")
    ]

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            Text(
                content=f"LazyColumn — {state.loaded} / {_TOTAL} loaded",
                style=Style(font_size=20.0),
            ),
            LazyColumn(
                item_count=state.loaded,
                item_builder=build_row,
                refreshing=state.refreshing,
                end_reached_threshold=0.8,
                on_end_reached=on_end_reached,
                on_refresh=on_refresh,
                style=Style(grow=1.0),
            ),
            Text(content="SectionList (sticky headers)", style=Style(font_size=20.0)),
            SectionList(sections=sections, style=Style(grow=1.0)),
        ],
    )


def main() -> int:
    """Run the lists demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — lists", size=(380, 720))


if __name__ == "__main__":
    raise SystemExit(main())
