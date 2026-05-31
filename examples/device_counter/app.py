"""A counter app for the device (phase B5 code-push target).

Unlike examples/counter/app.py, this imports no Qt — it runs on the Android host
via `tempest serve`, which pushes this source to the device's code-push client.
The contract is the same as the dev cockpit: `make_state()` + `view(app)`.

    adb reverse tcp:8765 tcp:8765
    uv run tempest serve examples/device_counter/app.py
    adb shell am start -n org.tempestroid.host/.MainActivity \
        --es tempest_dev_url http://localhost:8765
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import App, Button, Color, Column, Edge, Style, Text, Widget


@dataclass
class State:
    value: int = 0


def make_state() -> State:
    return State()


def _increment(state: State) -> None:
    state.value += 1


def view(app: App[State]) -> Widget:
    return Column(
        style=Style(
            padding=Edge.all(24),
            gap=16,
            background=Color(r=240, g=240, b=255),
        ),
        children=[
            Text(
                content=f"pushed count = {app.state.value}",
                style=Style(font_size=28, color=Color(r=20, g=20, b=40)),
            ),
            Button(label="increment", on_click=lambda: app.set_state(_increment)),
        ],
    )
