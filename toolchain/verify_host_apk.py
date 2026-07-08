"""Verify a built host APK bundles a ``tempest_core`` that satisfies the imports.

Guards against the class of release regression where the host APK ships a
``tempest_core`` out of sync with the ``tempestroid`` baked next to it — e.g. the
v0.15.2 host APK shipped a pre-``Alert`` ``tempest_core`` while ``tempestroid``
did ``from tempest_core.components import Alert``, so the app crashed on device
with ``ImportError: cannot import name 'Alert'`` (a blank/absent screen).

The check is static and host-side (no device, no Android import): it collects
every ``from tempest_core.<sub> import <names>`` in the ``tempestroid`` source
tree, then confirms each imported name is a top-level export of the matching
module *inside the APK's bundled ``tempest_core``*. Any missing name fails the
build before it can be released.

Usage::

    python toolchain/verify_host_apk.py <path-to-host.apk> [--src tempestroid]
"""

from __future__ import annotations

import argparse
import ast
import sys
import zipfile
from pathlib import Path

#: Marker of the bundled site-packages inside the host APK's assets.
_SITE_PACKAGES_MARKER = "/site-packages/"


def _iter_tempest_core_imports(
    src_root: Path,
) -> dict[str, set[str]]:
    """Collect ``from tempest_core.<sub> import <names>`` across the source tree.

    Args:
        src_root: The ``tempestroid`` package source directory.

    Returns:
        A mapping of submodule dotted path (e.g. ``tempest_core.components``) to
        the set of names imported from it anywhere in the tree. Star imports and
        bare ``import tempest_core`` are ignored (nothing to name-check).
    """
    wanted: dict[str, set[str]] = {}
    for py in src_root.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            mod = node.module or ""
            if mod != "tempest_core" and not mod.startswith("tempest_core."):
                continue
            names = {a.name for a in node.names if a.name != "*"}
            if names:
                wanted.setdefault(mod, set()).update(names)
    return wanted


def _exported_names(source: str) -> set[str]:
    """Return the top-level names a module source defines or re-exports.

    Covers the patterns a ``tempest_core`` package ``__init__`` uses to surface
    its API: ``def``/``class`` definitions, module-level assignments,
    ``from .x import Name`` re-exports, and explicit ``__all__`` entries.

    Args:
        source: The module's Python source.

    Returns:
        The set of names importable from the module at top level.
    """
    names: set[str] = set()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                    if target.id == "__all__" and isinstance(
                        node.value, (ast.List, ast.Tuple)
                    ):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                names.add(elt.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _read_bundled_module(zf: zipfile.ZipFile, dotted: str) -> str | None:
    """Read the source of a bundled ``tempest_core`` submodule from the APK.

    Args:
        zf: The opened host APK zip.
        dotted: A dotted module path such as ``tempest_core.components``.

    Returns:
        The module source, or ``None`` if neither ``<mod>.py`` nor
        ``<mod>/__init__.py`` is present in the bundled site-packages.
    """
    rel = dotted.replace(".", "/")
    candidates = (f"{rel}.py", f"{rel}/__init__.py")
    for entry in zf.namelist():
        if _SITE_PACKAGES_MARKER not in entry:
            continue
        tail = entry.split(_SITE_PACKAGES_MARKER, 1)[1]
        if tail in candidates:
            return zf.read(entry).decode("utf-8", "replace")
    return None


def verify(apk_path: Path, src_root: Path) -> list[str]:
    """Check the APK's bundled ``tempest_core`` satisfies ``tempestroid`` imports.

    Args:
        apk_path: Path to the built host APK.
        src_root: The ``tempestroid`` package source directory.

    Returns:
        A list of human-readable problems (empty when the APK is consistent).
    """
    problems: list[str] = []
    wanted = _iter_tempest_core_imports(src_root)
    with zipfile.ZipFile(apk_path) as zf:
        has_core = any(
            f"{_SITE_PACKAGES_MARKER}tempest_core/__init__.py" in n
            for n in zf.namelist()
        )
        if not has_core:
            return ["APK bundles no tempest_core under site-packages/"]
        for dotted, names in sorted(wanted.items()):
            source = _read_bundled_module(zf, dotted)
            if source is None:
                problems.append(f"{dotted}: module missing from bundled tempest_core")
                continue
            try:
                exported = _exported_names(source)
            except SyntaxError as exc:
                problems.append(f"{dotted}: unparseable in APK ({exc})")
                continue
            missing = sorted(names - exported)
            if missing:
                problems.append(
                    f"{dotted}: bundled tempest_core is missing "
                    f"{', '.join(missing)} (imported by tempestroid)"
                )
    return problems


def main() -> int:
    """CLI entry point: verify the host APK, printing PASS/FAIL.

    Returns:
        Process exit code — ``0`` when consistent, ``1`` on any mismatch.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="Path to the built host APK.")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("tempestroid"),
        help="tempestroid package source dir (default: ./tempestroid).",
    )
    args = parser.parse_args()

    if not args.apk.is_file():
        print(f"verify-host: APK not found: {args.apk}", file=sys.stderr)
        return 1

    problems = verify(args.apk, args.src)
    if problems:
        print(f"verify-host: FAIL — {args.apk.name} is out of sync:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "  Re-stage deps (make toolchain / 02_stage_deps.sh) and rebuild "
            "the host APK (make apk) so its tempest_core matches tempestroid.",
            file=sys.stderr,
        )
        return 1

    print(f"verify-host: OK — {args.apk.name} bundles a consistent tempest_core.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
