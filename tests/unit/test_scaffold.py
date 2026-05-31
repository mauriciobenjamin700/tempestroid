"""Tests for ``tempest new`` project scaffolding."""

from pathlib import Path

import pytest

from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.scaffold import scaffold
from tempestroid.core.state import App


def test_scaffold_creates_files(tmp_path: Path):
    root = scaffold("MyApp", parent=tmp_path)
    assert root == tmp_path / "MyApp"
    assert (root / "app.py").is_file()
    assert (root / "README.md").is_file()


def test_scaffolded_app_is_runnable(tmp_path: Path):
    # The generated app must honor the make_state + view contract and build.
    root = scaffold("Counter", parent=tmp_path)
    spec = load_app_spec(root / "app.py")
    app: App[object] = App(
        spec.make_state(), spec.view, apply_patches=lambda _patches: None
    )
    node = app.start()
    assert node is not None


def test_scaffold_app_uses_project_name(tmp_path: Path):
    root = scaffold("Greeter", parent=tmp_path)
    source = (root / "app.py").read_text(encoding="utf-8")
    assert "Greeter" in source


@pytest.mark.parametrize("bad", ["1abc", "with space", "-dash", "weird!", ""])
def test_scaffold_rejects_bad_name(tmp_path: Path, bad: str):
    with pytest.raises(ValueError):
        scaffold(bad, parent=tmp_path)


def test_scaffold_refuses_existing_dir(tmp_path: Path):
    (tmp_path / "dup").mkdir()
    with pytest.raises(FileExistsError):
        scaffold("dup", parent=tmp_path)
