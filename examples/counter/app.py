"""Interactive counter app (phases A1–A4).

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/counter/app.py

Tapping the buttons mutates state and triggers a coalesced rebuild; the diff is
applied to the live widgets. Handlers may be sync or ``async`` — see the "+ (async)"
button, which `await`s before updating.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    Edge,
    FlexDirection,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    """The counter's mutable state.

    Attributes:
        value: The current count.
    """

    value: int = 0


def make_state() -> CounterState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new counter state at zero.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Build the counter UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the counter screen.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    async def increment_later() -> None:
        await asyncio.sleep(0.5)
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        style=Style(
            direction=FlexDirection.COLUMN,
            align=AlignItems.CENTER,
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#101418"),
        ),
        children=[
            Text(
                content=f"Count: {app.state.value}",
                style=Style(
                    color=Color.from_hex("#ffffff"),
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="label",
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                    Button(label="+ (async)", on_click=increment_later, key="async"),
                ],
            ),
        ],
    )


def main() -> int:
    """Run the counter in the Qt simulator.

    Returns:
        The process exit code.
    """
    return run_qt(make_state(), view, title="tempestroid — counter", size=(320, 200))


if __name__ == "__main__":
    raise SystemExit(main())
