from pathlib import Path

import pytest

from tempestroid import App
from tempestroid.cli.app_loader import load_app_spec

_APP_TEMPLATE = """\
from dataclasses import dataclass

from tempestroid import App, Text, Widget


@dataclass
class State:
    label: str = "{label}"


def make_state() -> State:
    return State()


def view(app: "App[State]") -> Widget:
    return Text(content=app.state.label)
"""


def _write_app(path: Path, label: str) -> None:
    path.write_text(_APP_TEMPLATE.format(label=label), encoding="utf-8")


def test_load_app_spec_exposes_view_and_state(tmp_path: Path):
    app_file = tmp_path / "app.py"
    _write_app(app_file, "first")
    spec = load_app_spec(app_file)
    app: App[object] = App(spec.make_state(), spec.view, apply_patches=lambda p: None)
    scene = app.start()
    assert scene.root.props["content"] == "first"


def test_reload_picks_up_edits(tmp_path: Path):
    app_file = tmp_path / "app.py"
    _write_app(app_file, "v1")
    spec1 = load_app_spec(app_file)
    assert spec1.make_state().label == "v1"

    _write_app(app_file, "v2")
    spec2 = load_app_spec(app_file)
    assert spec2.make_state().label == "v2"


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_app_spec(tmp_path / "nope.py")


def test_missing_view_raises(tmp_path: Path):
    app_file = tmp_path / "bad.py"
    app_file.write_text("def make_state():\n    return None\n", encoding="utf-8")
    with pytest.raises(AttributeError):
        load_app_spec(app_file)
