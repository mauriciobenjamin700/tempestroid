"""Minimal device-only counter (phase B5 code-push target).

Unlike ``examples/counter/app.py``, this imports no Qt — it runs on the Android
host via ``tempest serve``, which pushes this source to the device's code-push
client and ``exec``s it where Qt is absent. The contract is the same as the dev
cockpit: ``make_state()`` + ``view(app)``. It uses only widgets and style fields
the Compose renderer already handles, and gives the button an explicit
background so it does not fall back to the host's Material default.

    adb reverse tcp:8765 tcp:8765
    uv run tempest serve examples/device_counter/app.py
    adb shell am start -n org.tempestroid.host/.MainActivity \
        --es tempest_dev_url http://localhost:8765
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
    Style,
    Text,
    Widget,
)


@dataclass
class CounterState:
    """The device counter's mutable state.

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


def _increment(state: CounterState) -> None:
    """Bump the counter by one.

    Args:
        state: The state to mutate.
    """
    state.value += 1


def view(app: App[CounterState]) -> Widget:
    """Build the device counter UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the counter screen.
    """
    return Column(
        style=Style(
            padding=Edge.all(24.0),
            gap=16.0,
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content=f"pushed count = {app.state.value}",
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#f9fafb"),
                ),
                key="display",
            ),
            Button(
                label="increment",
                on_click=lambda: app.set_state(_increment),
                key="increment",
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=18.0),
                    radius=10.0,
                    background=Color.from_hex("#2563eb"),
                    color=Color.from_hex("#ffffff"),
                ),
            ),
        ],
    )
