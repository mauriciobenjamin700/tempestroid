import asyncio
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.watcher import watch
from tempestroid.renderers.qt import Simulator

pytestmark = pytest.mark.usefixtures("qapp")

_APP = """\
from dataclasses import dataclass

from tempestroid import App, Column, Text, Widget


@dataclass
class State:
    value: int = 0


def make_state() -> State:
    return State()


def view(app: "App[State]") -> Widget:
    return Column(children=[Text(content="{text}")])
"""


def _labels(sim: Simulator) -> list[str]:
    return [label.text() for label in sim.renderer.root_widget.findChildren(QLabel)]


def test_load_renders_app(tmp_path: Path):
    app_file = tmp_path / "app.py"
    app_file.write_text(_APP.format(text="hello"), encoding="utf-8")
    sim = Simulator()
    sim.load(load_app_spec(app_file))
    assert _labels(sim) == ["hello"]


def test_hot_restart_after_edit_shows_new_ui(tmp_path: Path):
    """The A5 deliverable: edit app.py, reload, restart → new UI."""
    app_file = tmp_path / "app.py"
    app_file.write_text(_APP.format(text="before"), encoding="utf-8")
    sim = Simulator()
    sim.load(load_app_spec(app_file))
    assert _labels(sim) == ["before"]

    app_file.write_text(_APP.format(text="after"), encoding="utf-8")
    sim.load(load_app_spec(app_file))  # hot restart
    assert _labels(sim) == ["after"]


def test_restart_resets_state(tmp_path: Path):
    app_file = tmp_path / "app.py"
    app_file.write_text(_APP.format(text="x"), encoding="utf-8")
    sim = Simulator()
    sim.load(load_app_spec(app_file))
    sim.app.state.value = 42  # mutate directly (no running loop in this test)
    assert sim.app.state.value == 42

    sim.load(load_app_spec(app_file))  # restart → clean state
    assert sim.app.state.value == 0


async def test_watcher_triggers_hot_restart(tmp_path: Path):
    """End-to-end: saving the file auto-restarts the sim (the `run_dev` path)."""
    app_file = tmp_path / "app.py"
    app_file.write_text(_APP.format(text="before"), encoding="utf-8")
    sim = Simulator()
    sim.load(load_app_spec(app_file))
    assert _labels(sim) == ["before"]

    async def on_change() -> None:
        sim.load(load_app_spec(app_file))

    task = asyncio.create_task(watch([app_file], on_change, interval=0.02))
    await asyncio.sleep(0.05)
    app_file.write_text(_APP.format(text="after"), encoding="utf-8")
    bumped = os.stat(app_file).st_mtime + 5
    os.utime(app_file, (bumped, bumped))

    for _ in range(100):
        await asyncio.sleep(0.02)
        if _labels(sim) == ["after"]:
            break
    task.cancel()
    assert _labels(sim) == ["after"]
