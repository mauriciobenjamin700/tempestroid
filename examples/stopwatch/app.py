"""Async stopwatch — gallery example.

Demonstrates the async-first event loop: the "start" handler is a coroutine that
``await``s ``asyncio.sleep`` in a loop, calling ``set_state`` each tick. The UI
keeps responding (stop/reset stay tappable) and rebuilds are coalesced.

Runs in the Qt simulator::

    uv run python examples/stopwatch/app.py

and on a device via code-push::

    uv run tempest serve examples/stopwatch/app.py
"""

from __future__ import annotations

import asyncio
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

_TICK_SECONDS: float = 0.1


@dataclass
class StopwatchState:
    """The stopwatch's mutable state.

    Attributes:
        elapsed: Seconds elapsed (to one decimal place).
        running: Whether the ticking loop is active.
    """

    elapsed: float = 0.0
    running: bool = False


def make_state() -> StopwatchState:
    """Build a fresh initial state at zero, stopped.

    Returns:
        A new stopwatch state.
    """
    return StopwatchState()


def _format(elapsed: float) -> str:
    """Render seconds as ``mm:ss.t``."""
    minutes = int(elapsed) // 60
    seconds = int(elapsed) % 60
    tenths = int(round((elapsed - int(elapsed)) * 10)) % 10
    return f"{minutes:02d}:{seconds:02d}.{tenths}"


def view(app: App[StopwatchState]) -> Widget:
    """Build the stopwatch UI for the current state.

    Args:
        app: The running app.

    Returns:
        The root widget of the stopwatch screen.
    """

    async def start() -> None:
        """Tick the elapsed time until stopped (coroutine handler)."""
        if app.state.running:
            return
        app.set_state(lambda s: setattr(s, "running", True))
        while app.state.running:
            await asyncio.sleep(_TICK_SECONDS)
            app.set_state(
                lambda s: setattr(s, "elapsed", round(s.elapsed + _TICK_SECONDS, 1))
            )

    def stop() -> None:
        app.set_state(lambda s: setattr(s, "running", False))

    def _do_reset(s: StopwatchState) -> None:
        s.running = False
        s.elapsed = 0.0

    def reset() -> None:
        app.set_state(_do_reset)

    running = app.state.running
    display_color = Color.from_hex("#34d399") if running else Color.from_hex("#f9fafb")
    toggle_bg = Color.from_hex("#ef4444") if running else Color.from_hex("#22c55e")

    return Column(
        style=Style(
            gap=20.0,
            padding=Edge.all(28.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content=_format(app.state.elapsed),
                style=Style(
                    font_size=52.0,
                    font_weight=FontWeight.BOLD,
                    color=display_color,
                ),
                key="display",
            ),
            Row(
                style=Style(gap=12.0),
                children=[
                    Button(
                        label="stop" if running else "start",
                        on_click=stop if running else start,
                        key="toggle",
                        style=Style(
                            padding=Edge.symmetric(vertical=14.0, horizontal=24.0),
                            radius=10.0,
                            background=toggle_bg,
                            color=Color.from_hex("#ffffff"),
                            font_size=18.0,
                        ),
                    ),
                    Button(
                        label="reset",
                        on_click=reset,
                        key="reset",
                        style=Style(
                            padding=Edge.symmetric(vertical=14.0, horizontal=24.0),
                            radius=10.0,
                            background=Color.from_hex("#374151"),
                            color=Color.from_hex("#f9fafb"),
                            font_size=18.0,
                        ),
                    ),
                ],
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — stopwatch", size=(320, 240))
    )
