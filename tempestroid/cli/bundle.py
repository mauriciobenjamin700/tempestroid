"""Package a multi-file tempestroid project into a single transportable bundle.

A tempestroid app is rarely one file: ``main.py`` imports sibling modules and
packages from the project tree. Both device paths — the offline push
(``tempest deploy`` / ``tempest serve``) and the baked-in APK (``tempest build``)
— need the *whole* importable tree on the device, not just the entry file.

This module turns a project directory into a deterministic ``.zip`` (so an
unchanged tree always hashes the same, enabling cheap change-detection) carrying
a small ``tempest_bundle.json`` manifest that records the entry module. The
device side extracts it, puts the root on ``sys.path``, and execs the entry — so
``from my_pkg.foo import bar`` resolves exactly as it does on the desktop.

The project **root** is the nearest ancestor of the app file containing a
``pyproject.toml`` (the import anchor), falling back to the app file's own
directory. The entry is recorded relative to that root.
"""

from __future__ import annotations

import hashlib
import io
import json
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MANIFEST_NAME",
    "ProjectLayout",
    "resolve_project",
    "build_bundle",
    "bundle_hash",
    "tree_signature",
    "extract_bundle",
]

# Manifest file written at the bundle root recording the entry module.
MANIFEST_NAME = "tempest_bundle.json"

# Directory/file names never shipped: virtualenvs, caches, VCS, build output,
# editor metadata. They are huge and/or irrelevant to running the app, and the
# `tempestroid` package itself already lives on the device.
_EXCLUDED_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        ".idea",
        ".vscode",
        ".gradle",
        ".eggs",
    }
)
_EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".apk", ".so"})
# A fixed timestamp so byte-identical content always yields the same archive
# (and thus the same hash) regardless of file mtimes.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class ProjectLayout:
    """Where a project's importable root is and which module is its entry.

    Attributes:
        root: The project root directory placed on ``sys.path`` on the device.
        entry: The entry module path, relative to ``root`` (e.g. ``"main.py"``).
    """

    root: Path
    entry: str


#: The framework's own distribution names. A ``pyproject.toml`` declaring one of
#: these is NOT an app project — it's the framework/engine repo itself. Running
#: the bundled ``examples/`` through ``resolve_project`` must NOT anchor to the
#: framework repo root, or ``tree_signature``/``build_bundle`` would walk the
#: entire repo (docs assets, android-host, every other example) — slow enough to
#: blow the code-push poll timeout, and a wrong, huge bundle. The framework is
#: already staged on the device; an example bundles only its own directory.
_FRAMEWORK_PROJECT_NAMES = frozenset({"tempestroid", "tempest-core", "tempestweb"})


def _is_framework_pyproject(pyproject: Path) -> bool:
    """Report whether a ``pyproject.toml`` declares the framework itself.

    Args:
        pyproject: Path to a ``pyproject.toml`` file.

    Returns:
        ``True`` when its ``[project].name`` is one of the framework packages,
        so it should be skipped as a project-root anchor for an app bundle.
    """
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    name = data.get("project", {}).get("name", "")
    return isinstance(name, str) and name.strip().lower() in _FRAMEWORK_PROJECT_NAMES


def resolve_project(app: str | Path) -> ProjectLayout:
    """Resolve a project's root + entry from an app file path.

    The root is the nearest ancestor directory of ``app`` that contains a
    ``pyproject.toml`` (the import anchor), **skipping the framework's own
    ``pyproject.toml``** (so the bundled ``examples/`` anchor to their own
    directory, not the whole framework repo); if none is found, the app file's
    own directory is used. The entry is ``app`` relative to that root.

    Args:
        app: Path to the app's entry Python file (defines ``view`` +
            ``make_state``).

    Returns:
        The resolved :class:`ProjectLayout`.

    Raises:
        FileNotFoundError: If ``app`` does not exist.
    """
    entry_file = Path(app).resolve()
    if not entry_file.is_file():
        raise FileNotFoundError(f"app file not found: {entry_file}")
    root = entry_file.parent
    for directory in (entry_file.parent, *entry_file.parents):
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file() and not _is_framework_pyproject(pyproject):
            root = directory
            break
    return ProjectLayout(root=root, entry=str(entry_file.relative_to(root)))


def _included_files(root: Path) -> list[Path]:
    """List the files under ``root`` belonging in a bundle, in stable order.

    Args:
        root: The project root to walk.

    Returns:
        Included files sorted by their root-relative POSIX path.
    """
    return sorted(
        (p for p in root.rglob("*") if p.is_file() and _should_include(p, root)),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def _should_include(path: Path, root: Path) -> bool:
    """Decide whether a file under ``root`` belongs in the bundle.

    Args:
        path: The candidate file.
        root: The project root the bundle is built from.

    Returns:
        ``True`` to include the file, ``False`` to skip it.
    """
    rel_parts = path.relative_to(root).parts
    if any(part in _EXCLUDED_DIRS for part in rel_parts):
        return False
    if path.suffix in _EXCLUDED_SUFFIXES:
        return False
    return path.name != MANIFEST_NAME


def build_bundle(layout: ProjectLayout) -> bytes:
    """Build a deterministic ``.zip`` of the project tree plus a manifest.

    Walks ``layout.root`` (skipping virtualenvs, caches, VCS, build output —
    see :data:`_EXCLUDED_DIRS`), adds every remaining file under its
    root-relative path with a fixed timestamp, and appends a
    :data:`MANIFEST_NAME` recording the entry module. Byte-identical trees
    produce byte-identical archives, so :func:`bundle_hash` is a stable change
    key.

    Args:
        layout: The resolved project layout to package.

    Returns:
        The zip archive bytes.
    """
    files = _included_files(layout.root)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = json.dumps({"entry": layout.entry}, sort_keys=True)
        manifest_info = zipfile.ZipInfo(MANIFEST_NAME, date_time=_FIXED_DATE_TIME)
        archive.writestr(manifest_info, manifest)
        for file in files:
            rel = file.relative_to(layout.root).as_posix()
            info = zipfile.ZipInfo(rel, date_time=_FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file.read_bytes())
    return buffer.getvalue()


def bundle_hash(data: bytes) -> str:
    """Return the stable content hash of a bundle.

    Args:
        data: The bundle bytes from :func:`build_bundle`.

    Returns:
        A hex SHA-256 digest used to detect project changes.
    """
    return hashlib.sha256(data).hexdigest()


def tree_signature(layout: ProjectLayout) -> str:
    """Return a cheap change key for a project tree (no archive build).

    Hashes the sorted ``(relative path, size, mtime_ns)`` of every included file
    plus the entry name. Far cheaper than :func:`build_bundle`, so the dev
    server can answer ``/version`` polls every second by stat-ing the tree and
    only rebuild the actual archive when this signature changes.

    Args:
        layout: The resolved project layout to fingerprint.

    Returns:
        A hex SHA-256 digest that changes whenever any included file is added,
        removed, resized, or touched.
    """
    digest = hashlib.sha256()
    digest.update(layout.entry.encode())
    for file in _included_files(layout.root):
        stat = file.stat()
        rel = file.relative_to(layout.root).as_posix()
        digest.update(f"\0{rel}\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def extract_bundle(data: bytes, dest: Path) -> ProjectLayout:
    """Extract a bundle into ``dest`` and read its entry from the manifest.

    The device side calls this to materialize a pushed/baked project before
    placing ``dest`` on ``sys.path`` and loading the entry module.

    Args:
        data: The zip archive bytes.
        dest: The directory to extract into (created if missing; existing
            contents are left in place and overwritten per file).

    Returns:
        A :class:`ProjectLayout` whose ``root`` is ``dest`` and whose ``entry``
        is read from the manifest (defaulting to ``"main.py"``).
    """
    dest.mkdir(parents=True, exist_ok=True)
    entry = "main.py"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(dest)
        if MANIFEST_NAME in archive.namelist():
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            entry = str(manifest.get("entry", entry))
    return ProjectLayout(root=dest, entry=entry)
