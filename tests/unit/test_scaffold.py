"""Tests for ``tempest new`` project scaffolding."""

from pathlib import Path

import pytest
from tempest_core.core.state import App

from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.scaffold import scaffold


def test_scaffold_creates_files(tmp_path: Path):
    result = scaffold("MyApp", parent=tmp_path)
    assert result.root == tmp_path / "MyApp"
    assert result.in_place is False
    assert (result.root / "app.py").is_file()
    assert (result.root / "README.md").is_file()
    assert (result.root / "pyproject.toml").is_file()
    assert (result.root / ".gitignore").is_file()


def test_scaffold_pyproject_points_at_app(tmp_path: Path):
    result = scaffold("MyApp", parent=tmp_path)
    pyproject = (result.root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.tempest]" in pyproject
    assert 'app = "app.py"' in pyproject
    assert "tempestroid[qt]" in pyproject


def test_scaffold_in_place(tmp_path: Path):
    target = tmp_path / "my-cool-app"
    target.mkdir()
    result = scaffold(".", parent=target)
    assert result.in_place is True
    assert result.root == target
    assert (target / "app.py").is_file()
    # The project slug is derived from the directory name.
    pyproject = (target / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "my-cool-app"' in pyproject


def test_scaffold_in_place_refuses_existing_app(tmp_path: Path):
    (tmp_path / "app.py").write_text("# existing\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold(".", parent=tmp_path)


def test_scaffolded_app_is_runnable(tmp_path: Path):
    # The generated app must honor the make_state + view contract and build.
    result = scaffold("Counter", parent=tmp_path)
    spec = load_app_spec(result.root / "app.py")
    app: App[object] = App(
        spec.make_state(), spec.view, apply_patches=lambda _patches: None
    )
    node = app.start()
    assert node is not None


def test_scaffold_app_uses_project_name(tmp_path: Path):
    result = scaffold("Greeter", parent=tmp_path)
    source = (result.root / "app.py").read_text(encoding="utf-8")
    assert "Greeter" in source


@pytest.mark.parametrize("bad", ["1abc", "with space", "-dash", "weird!", ""])
def test_scaffold_rejects_bad_name(tmp_path: Path, bad: str):
    with pytest.raises(ValueError):
        scaffold(bad, parent=tmp_path)


def test_scaffold_refuses_existing_dir(tmp_path: Path):
    (tmp_path / "dup").mkdir()
    with pytest.raises(FileExistsError):
        scaffold("dup", parent=tmp_path)
