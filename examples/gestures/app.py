"""Advanced gestures demo — swipe-to-delete, drag-to-reorder, pinch-to-zoom (E4).

Showcases the phase-E4 gesture widgets:

- :class:`~tempestroid.Dismissible` — swipe an item to delete it (``on_dismiss``).
- :class:`~tempestroid.ReorderableList` — drag items into a new order
  (``on_reorder`` with ``from_index``/``to_index``; reuses the keyed ``Reorder``
  diff from A2).
- :class:`~tempestroid.InteractiveViewer` — pan + pinch-zoom a child.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/gestures/app.py

Or on a device via code-push::

    uv run tempest serve examples/gestures/app.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    Color,
    Column,
    Dismissible,
    Edge,
    InteractiveViewer,
    ReorderableList,
    ReorderEvent,
    Style,
    Text,
    Widget,
)


@dataclass
class GestureState:
    """The demo's mutable state.

    Attributes:
        items: The labels currently shown (swipe to delete, drag to reorder).
        last_action: A human-readable note about the last gesture handled.
    """

    items: list[str] = field(
        default_factory=lambda: ["Alpha", "Bravo", "Charlie", "Delta"]
    )
    last_action: str = "swipe a row to delete, drag to reorder, pinch the box"


def make_state() -> GestureState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gesture state.
    """
    return GestureState()


def view(app: App[GestureState]) -> Widget:
    """Build the gestures UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the gestures screen.
    """
    state = app.state

    def on_dismiss_item(label: str) -> None:
        def remove(s: GestureState) -> None:
            s.items = [item for item in s.items if item != label]
            s.last_action = f"dismissed {label}"

        app.set_state(remove)

    def on_reorder(event: ReorderEvent) -> None:
        def reorder(s: GestureState) -> None:
            items = list(s.items)
            items.insert(event.to_index, items.pop(event.from_index))
            s.items = items
            s.last_action = f"moved {event.from_index} -> {event.to_index}"

        app.set_state(reorder)

    def row(label: str) -> Widget:
        return Dismissible(
            key=label,
            on_dismiss=lambda _event, label=label: on_dismiss_item(label),
            child=Text(
                content=label,
                style=Style(
                    padding=Edge.all(16.0),
                    background=Color.from_hex("#1b2733"),
                    color=Color.from_hex("#ffffff"),
                    radius=8.0,
                ),
            ),
        )

    return Column(
        style=Style(gap=14.0, padding=Edge.all(16.0)),
        children=[
            Text(content="Gestures demo", style=Style(font_size=22.0)),
            Text(content=state.last_action),
            ReorderableList(
                on_reorder=on_reorder,
                children=[row(label) for label in state.items],
            ),
            Text(content="Pinch / drag the box:", style=Style(font_size=16.0)),
            InteractiveViewer(
                min_scale=0.5,
                max_scale=4.0,
                child=Column(
                    style=Style(
                        padding=Edge.all(40.0),
                        radius=12.0,
                        background=Color.from_hex("#6c4cf0"),
                    ),
                    children=[
                        Text(
                            content="zoom me",
                            style=Style(color=Color.from_hex("#ffffff")),
                        ),
                    ],
                ),
            ),
        ],
    )


def main() -> int:
    """Run the gestures demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — gestures", size=(380, 640))


if __name__ == "__main__":
    raise SystemExit(main())
