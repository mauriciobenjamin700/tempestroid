"""Tests for app-path resolution from project config (``[tool.tempest] app``)."""

from pathlib import Path

import pytest

from tempestroid.cli.project import AppResolutionError, resolve_app


def _write_project(root: Path, app: str = "app.py") -> None:
    """Write a minimal pyproject.toml with a [tool.tempest] app pointer."""
    root.joinpath("pyproject.toml").write_text(
        f'[project]\nname = "demo"\n\n[tool.tempest]\napp = "{app}"\n',
        encoding="utf-8",
    )


def test_resolve_explicit_arg_wins(tmp_path: Path):
    _write_project(tmp_path, "configured.py")
    assert resolve_app("explicit.py", start=tmp_path) == "explicit.py"


def test_resolve_reads_configured_app(tmp_path: Path):
    _write_project(tmp_path, "app.py")
    assert resolve_app(None, start=tmp_path) == str((tmp_path / "app.py").resolve())


def test_resolve_walks_up_to_project_root(tmp_path: Path):
    _write_project(tmp_path, "app.py")
    nested = tmp_path / "sub" / "dir"
    nested.mkdir(parents=True)
    assert resolve_app(None, start=nested) == str((tmp_path / "app.py").resolve())


def test_resolve_without_config_raises(tmp_path: Path):
    with pytest.raises(AppResolutionError):
        resolve_app(None, start=tmp_path)


def test_resolve_pyproject_without_tempest_table_raises(tmp_path: Path):
    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "demo"\n', encoding="utf-8"
    )
    with pytest.raises(AppResolutionError):
        resolve_app(None, start=tmp_path)
