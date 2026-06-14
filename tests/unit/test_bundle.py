"""Tests for the multi-file project bundle (build/extract/load) used on device.

These cover the desktop half: resolving a project's root + entry, building a
deterministic zip of the whole tree, hashing/fingerprinting it, extracting it
back, and loading a multi-file app via :func:`spec_from_project`. The device
just calls these (extract + load) over the JNI bridge.
"""

import io
import sys
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


# Entry imports a sibling by bare name (`from app import …`), and the entry lives
# in a subdirectory below the project root — the exact F9 emulator shape, where
# the resolved root (the pyproject dir) sits *above* the entry's own directory.
_SIBLING_APP_ENTRY = """
from app import make_state, view

__all__ = ["make_state", "view"]
"""

_SIBLING_APP_IMPL = """
from dataclasses import dataclass

from tempestroid import App, Text, Widget


@dataclass
class State:
    label: str = "sibling"


def make_state() -> State:
    return State()


def view(app: App[State]) -> Widget:
    return Text(content=app.state.label)
"""


def test_spec_from_project_adds_entry_parent_for_bare_sibling_import(
    tmp_path: Path,
) -> None:
    """An entry below the root that imports a bare sibling loads on the device path.

    Reproduces the F9 emulator bug: ``examples/counter/test_counter.py`` does
    ``from app import make_state, view`` (a sibling), but ``resolve_project`` picks
    the repo/``examples`` pyproject dir as root — *above* ``examples/counter/``.
    The headless runner inserts the entry's parent, so it worked in-process; the
    device/bundle path (``spec_from_project``) used to insert only the root, so the
    bare ``import app`` raised ``ModuleNotFoundError`` on device. The fix mirrors
    the entry's parent onto ``sys.path`` here too.
    """
    # Root carries the pyproject (the import anchor) but the entry + its sibling
    # live one level down, so root != entry parent.
    (tmp_path / "pyproject.toml").write_text(
        '[tool.tempest]\napp = "counter/entry.py"\n', encoding="utf-8"
    )
    sub = tmp_path / "counter"
    sub.mkdir()
    (sub / "app.py").write_text(_SIBLING_APP_IMPL, encoding="utf-8")
    (sub / "entry.py").write_text(_SIBLING_APP_ENTRY, encoding="utf-8")

    entry_parent = str(sub.resolve())
    sys.path[:] = [p for p in sys.path if p != entry_parent]
    try:
        # Loading without ModuleNotFoundError proves the entry parent landed on
        # sys.path so the bare `from app import …` resolved.
        spec = spec_from_project(
            tmp_path, "counter/entry.py", name="_tempest_sibling_test"
        )
        assert entry_parent in sys.path
        assert spec.make_state().label == "sibling"
        rendered = spec.view(_StubApp(spec.make_state()))  # type: ignore[arg-type]
        assert isinstance(rendered, Text)
        assert rendered.content == "sibling"
        # Idempotent: a second load must not duplicate the entry parent entry.
        spec_from_project(tmp_path, "counter/entry.py", name="_tempest_sibling_test")
        assert sys.path.count(entry_parent) == 1
    finally:
        sys.path[:] = [p for p in sys.path if p != entry_parent]
        sys.modules.pop("_tempest_sibling_test", None)
        sys.modules.pop("app", None)


def test_stage_app_bundle_writes_zip_asset(tmp_path: Path) -> None:
    app = _make_project(tmp_path)
    host = tmp_path / "android-host"
    host.mkdir()
    asset = stage_app_bundle(app, host)
    assert asset == host / "app" / "src" / "main" / "assets" / "tempest_app_bundle.zip"
    assert asset.is_file()
    with zipfile.ZipFile(asset) as archive:
        assert "widgets_lib/greeting.py" in archive.namelist()
