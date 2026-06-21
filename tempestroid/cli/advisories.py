"""Developer advisories raised while loading an app's source.

Some Python libraries are a poor fit for a tempestroid app — they are heavy on
Android, or a lighter alternative exists that actually runs on device. Rather than
fail (the import may still work in the Qt simulator), the loader scans the source
and emits a guidance :mod:`warnings` advisory so the developer is steered toward
the recommended choice early — in the dev sim AND over the device code-push path
(both funnel through :func:`tempestroid.cli.app_loader.spec_from_source`).

Currently one advisory: **pandas → polars**. pandas drags large Cython/C
extensions (and its scientific deps) into the APK and is awkward to cross-compile;
polars is a Rust-core DataFrame that cross-compiles to an ``abi3`` Android wheel,
has a dependency-free core, and reads/writes CSV/JSON/Parquet natively. See
``docs/research/g-polars-feasibility.md``.
"""

from __future__ import annotations

import ast
import warnings

__all__ = [
    "DiscouragedImportWarning",
    "DISCOURAGED_IMPORTS",
    "scan_imported_roots",
    "advisories_for_source",
    "warn_discouraged_imports",
]


class DiscouragedImportWarning(UserWarning):
    """Warning category for an import a tempestroid app should avoid."""


#: Top-level module name -> guidance shown when an app imports it. Keep the
#: messages short and actionable (what to use instead + why).
DISCOURAGED_IMPORTS: dict[str, str] = {
    "pandas": (
        "pandas is a heavy fit for a tempestroid app — it pulls large Cython/C "
        "extensions (and its scientific deps) into the APK and is awkward to "
        "cross-compile for Android. Prefer polars: a Rust-core DataFrame that "
        "runs on device (abi3 wheel, dependency-free core, native CSV/JSON/"
        "Parquet read/write). See docs/research/g-polars-feasibility.md."
    ),
}


def scan_imported_roots(source: str) -> set[str]:
    """Return the set of top-level module names imported anywhere in ``source``.

    Parses the source and walks **every** ``import`` / ``from ... import`` node
    (module level and nested inside functions, so an ``import pandas`` inside a
    handler is still found), reducing each to its top-level package (``pandas``
    from ``pandas.api.types``). Returns an empty set when the source does not
    parse — a syntax error surfaces elsewhere (the real exec), not here.

    Args:
        source: The app module's Python source.

    Returns:
        The set of imported top-level module names.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports (node.level > 0) — they target the app's own
            # package, never a discouraged top-level dependency.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def advisories_for_source(source: str) -> list[str]:
    """Return the advisory messages for discouraged imports found in ``source``.

    Args:
        source: The app module's Python source.

    Returns:
        One message per discouraged module the source imports, sorted by module
        name (empty when none — the common case).
    """
    roots = scan_imported_roots(source)
    found = sorted(roots & DISCOURAGED_IMPORTS.keys())
    return [DISCOURAGED_IMPORTS[name] for name in found]


def warn_discouraged_imports(
    source: str, *, filename: str = "<tempest-app>"
) -> list[str]:
    """Emit a :class:`DiscouragedImportWarning` for each discouraged import.

    Called by the app loader on every load (sim + device code-push) so the nudge
    reaches the developer where they work. Returns the messages too, so a caller
    that prefers its own reporting channel can surface them instead.

    Args:
        source: The app module's Python source.
        filename: A label for the source (a path or synthetic name), prefixed onto
            each warning so the developer knows which file triggered it.

    Returns:
        The advisory messages emitted (empty when none).
    """
    messages = advisories_for_source(source)
    for message in messages:
        warnings.warn(f"{filename}: {message}", DiscouragedImportWarning, stacklevel=2)
    return messages
