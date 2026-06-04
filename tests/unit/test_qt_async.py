import asyncio
from dataclasses import dataclass

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from tempestroid import App, Button, Column, Text, Widget
from tempestroid.renderers.qt import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")


@dataclass
class Counter:
    value: int = 0


def _labels(renderer: QtRenderer) -> list[str]:
    return [label.text() for label in renderer.root_widget.findChildren(QLabel)]


def _button(renderer: QtRenderer) -> QPushButton:
    button = renderer.root_widget.findChild(QPushButton)
    assert isinstance(button, QPushButton)
    return button


async def test_async_handler_awaits_then_updates_screen():
    renderer = QtRenderer()

    def view(app: "App[Counter]") -> Widget:
        async def increment() -> None:
            await asyncio.sleep(0.02)
            app.set_state(lambda s: setattr(s, "value", s.value + 1))

        return Column(
            children=[
                Text(content=f"Count: {app.state.value}"),
                Button(label="+", on_click=increment, key="inc"),
            ]
        )

    app: App[Counter] = App(Counter(), view, apply_patches=renderer.apply)
    renderer.mount(app.start().root)
    assert _labels(renderer) == ["Count: 0"]

    _button(renderer).click()  # schedules the async handler as a loop task
    await asyncio.sleep(0.1)  # let the await complete and the rebuild run

    assert _labels(renderer) == ["Count: 1"]


async def test_sync_handler_updates_screen_on_next_tick():
    renderer = QtRenderer()

    def view(app: "App[Counter]") -> Widget:
        return Column(
            children=[
                Text(content=f"Count: {app.state.value}"),
                Button(
                    label="+",
                    on_click=lambda: app.set_state(
                        lambda s: setattr(s, "value", s.value + 1)
                    ),
                    key="inc",
                ),
            ]
        )

    app: App[Counter] = App(Counter(), view, apply_patches=renderer.apply)
    renderer.mount(app.start().root)

    _button(renderer).click()
    await asyncio.sleep(0)  # rebuild is coalesced onto the loop

    assert _labels(renderer) == ["Count: 1"]
