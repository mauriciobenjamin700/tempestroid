"""Tests for the multi-file project bundle (build/extract/load) used on device.

These cover the desktop half: resolving a project's root + entry, building a
deterministic zip of the whole tree, hashing/fingerprinting it, extracting it
back, and loading a multi-file app via :func:`spec_from_project`. The device
just calls these (extract + load) over the JNI bridge.
"""

import io
import zipfile
from pathlib import Path

import pytest

from tempestroid import Text
from tempestroid.cli.app_loader import spec_from_project
from tempestroid.cli.bundle import (
    MANIFEST_NAME,
    build_bundle,
    bundle_hash,
    extract_bundle,
    resolve_project,
    tree_signature,
)
from tempestroid.cli.packaging import stage_app_bundle

_MULTI_FILE_APP = """
from dataclasses import dataclass

from widgets_lib.greeting import greeting
from tempestroid import App, Text, Widget


@dataclass
class State:
    name: str = "world"


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    return Text(content=greeting(app.state.name))
"""

_GREETING_MODULE = 'def greeting(name: str) -> str:\n    return f"hi {name}"\n'


class _StubApp:
    """Minimal app stand-in exposing ``.state`` for a view() call in tests."""

    def __init__(self, state: object) -> None:
        self.state = state


def _make_project(root: Path) -> Path:
    """Create a 2-file project (app.py importing widgets_lib.greeting)."""
    (root / "pyproject.toml").write_text(
        '[tool.tempest]\napp = "app.py"\n', encoding="utf-8"
    )
    (root / "app.py").write_text(_MULTI_FILE_APP, encoding="utf-8")
    pkg = root / "widgets_lib"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "greeting.py").write_text(_GREETING_MODULE, encoding="utf-8")
    return root / "app.py"


def test_resolve_project_uses_pyproject_as_root(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    layout = resolve_project(app)
    assert layout.root == tmp_path.resolve()
    assert layout.entry == "app.py"


def test_resolve_project_missing_app_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_project(tmp_path / "nope.py")


def test_build_bundle_contains_tree_and_manifest(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    data = build_bundle(resolve_project(app))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert MANIFEST_NAME in names
    assert {"app.py", "widgets_lib/__init__.py", "widgets_lib/greeting.py"} <= names


def test_build_bundle_excludes_caches_and_venv(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"junk")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "big.py").write_text("import this\n", encoding="utf-8")
    data = build_bundle(resolve_project(app))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert not any(
        ".venv" in n or "__pycache__" in n or n.endswith(".pyc") for n in names
    )


def test_build_bundle_is_deterministic(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    layout = resolve_project(app)
    assert bundle_hash(build_bundle(layout)) == bundle_hash(build_bundle(layout))


def test_tree_signature_changes_on_edit(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    layout = resolve_project(app)
    before = tree_signature(layout)
    (tmp_path / "widgets_lib" / "greeting.py").write_text(
        'def greeting(name: str) -> str:\n    return f"hello there {name}!!!"\n',
        encoding="utf-8",
    )
    assert tree_signature(layout) != before


def test_extract_bundle_round_trips_entry(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    data = build_bundle(resolve_project(app))
    dest = tmp_path / "extracted"
    layout = extract_bundle(data, dest)
    assert layout.root == dest
    assert layout.entry == "app.py"
    assert (dest / "widgets_lib" / "greeting.py").is_file()


def test_spec_from_project_resolves_sibling_imports(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    data = build_bundle(resolve_project(app))
    dest = tmp_path / "extracted"
    layout = extract_bundle(data, dest)
    # The entry does `from widgets_lib.greeting import greeting` at module level,
    # so loading the spec without ImportError proves the tree is on sys.path.
    spec = spec_from_project(layout.root, layout.entry, name="_tempest_bundle_test")
    assert callable(spec.view)
    assert spec.make_state().name == "world"
    # The imported helper renders into the view's text.
    rendered = spec.view(_StubApp(spec.make_state()))  # type: ignore[arg-type]
    assert isinstance(rendered, Text)
    assert rendered.content == "hi world"


def test_stage_app_bundle_writes_zip_asset(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    host = tmp_path / "android-host"
    host.mkdir()
    asset = stage_app_bundle(app, host)
    assert asset == host / "app" / "src" / "main" / "assets" / "tempest_app_bundle.zip"
    assert asset.is_file()
    with zipfile.ZipFile(asset) as archive:
        assert "widgets_lib/greeting.py" in archive.namelist()
