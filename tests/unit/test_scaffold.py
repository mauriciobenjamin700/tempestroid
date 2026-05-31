"""Tests for ``tempest new`` scaffolding + stateful hot reload (phase C)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tempestroid import build
from tempestroid.cli.app_loader import load_app_spec
from tempestroid.cli.scaffold import scaffold_app
from tempestroid.core.state import App
from tempestroid.devserver.client import carry_state


def test_scaffold_creates_runnable_app(tmp_path: Path) -> None:
    """The scaffolded app satisfies the make_state + view contract and builds."""
    app_file = scaffold_app(tmp_path / "my_app")
    assert app_file.is_file()

    spec = load_app_spec(app_file)
    app: App[object] = App(spec.make_state(), spec.view, apply_patches=lambda _: None)
    node = build(spec.view(app))
    assert node.type == "Column"


def test_scaffold_refuses_overwrite(tmp_path: Path) -> None:
    """Scaffolding refuses to clobber an existing app.py."""
    scaffold_app(tmp_path / "app1")
    with pytest.raises(FileExistsError):
        scaffold_app(tmp_path / "app1")


def test_carry_state_preserves_common_fields() -> None:
    """Stateful reload copies shared fields and ignores removed/added ones."""

    @dataclass
    class Old:
        count: int = 0
        label: str = ""

    @dataclass
    class New:
        count: int = 0
        extra: bool = False

    old = Old(count=7, label="gone")
    new = New()
    carry_state(old, new)

    assert new.count == 7  # shared field carried over
    assert new.extra is False  # new field keeps its fresh default
    assert not hasattr(new, "label")  # removed field dropped
