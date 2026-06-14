"""Load a tempestroid app module and expose its view + state factory.

The dev cockpit reloads the user's app on every save, so loading must be cheap,
repeatable and free of side effects. The contract a runnable app module must
satisfy:

* ``view``: ``Callable[[App[S]], Widget]`` — builds the UI from the app.
* ``make_state``: ``Callable[[], S]`` — produces a *fresh* initial state, so a
  hot restart starts clean.

Each load compiles and execs the file fresh (no ``.pyc`` reuse), so editing and
reloading always picks up the change even within one mtime tick. The throwaway
module is registered under a stable name in ``sys.modules`` only so decorators
that resolve ``sys.modules[__module__]`` (e.g. ``@dataclass``) work; a reload
overwrites that entry on purpose.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from tempest_core.core.state import App
from tempest_core.widgets import Widget

__all__ = ["AppSpec", "load_app_spec", "spec_from_project", "spec_from_source"]


@dataclass(frozen=True)
class AppSpec:
    """A loaded app's entry points.

    Attributes:
        make_state: Factory returning a fresh initial state.
        view: Builds the widget tree from the running app.
    """

    make_state: Callable[[], Any]
    view: Callable[[App[Any]], Widget]


def load_app_spec(path: str | Path) -> AppSpec:
    """Load an app module from a file path and extract its spec.

    Args:
        path: Path to the app's Python file (e.g. ``examples/counter/app.py``).

    Returns:
        The loaded :class:`AppSpec`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        AttributeError: If the module lacks ``view`` or ``make_state``.
        TypeError: If ``view`` or ``make_state`` is not callable.
    """
    from tempestroid.cli.bundle import resolve_project

    file = Path(path).resolve()
    if not file.is_file():
        raise FileNotFoundError(f"app file not found: {file}")
    # Resolve the project root (nearest pyproject) and put it on sys.path, so a
    # multi-file app's sibling imports (`from my_pkg import x`) work in the Qt
    # simulator / dev loop exactly as they do on device. A lone file with no
    # pyproject resolves root = its own dir (harmless), preserving single-file.
    layout = resolve_project(file)
    return spec_from_project(
        layout.root, layout.entry, name=f"_tempest_app_{file.stem}"
    )


def spec_from_project(
    root: str | Path,
    entry: str,
    *,
    name: str = "_tempest_app",
) -> AppSpec:
    """Load an app spec from a multi-file project root + entry module.

    Puts both the project ``root`` *and* the entry module's own parent directory
    on ``sys.path`` (so ``entry``'s absolute imports resolve whether the sibling
    lives at the project root — ``from src.foo import x`` — or right next to the
    entry — ``from app import x``), then execs the entry module's source. This is
    the multi-file counterpart of :func:`load_app_spec`: the device side (baked
    APK or code-push) extracts a project bundle to ``root`` and calls this.

    Mirroring the entry parent onto ``sys.path`` keeps the on-device/bundle
    loader in parity with the in-process headless test runner
    (:mod:`tempestroid.testing.runner`), which already inserts the entry file's
    parent so a test/app entry can import a sibling module
    (``from app import view, make_state``). Without it, an entry that imports a
    sibling fails on device with ``ModuleNotFoundError`` whenever the resolved
    project root sits above the entry's own directory (e.g. the repo root or
    ``examples/`` for ``examples/counter/test_counter.py``).

    Args:
        root: The project root directory to place on ``sys.path``.
        entry: The entry module path, relative to ``root`` (e.g. ``"main.py"``).
        name: The throwaway module name registered in ``sys.modules``.

    Returns:
        The loaded :class:`AppSpec`.

    Raises:
        FileNotFoundError: If the entry module does not exist under ``root``.
        AttributeError: If the entry lacks ``view`` or ``make_state``.
        TypeError: If ``view`` or ``make_state`` is not callable.
    """
    root_path = Path(root).resolve()
    entry_file = (root_path / entry).resolve()
    if not entry_file.is_file():
        raise FileNotFoundError(f"app entry not found: {entry_file}")
    # Both dirs go on sys.path (additive + idempotent). The project root anchors
    # `from src.foo import x`; the entry's own parent anchors `from sibling import
    # x`. When root == entry parent (single-dir project) the dedupe collapses to
    # one insert. Keep the entry parent at index 0 so a sibling shadows nothing
    # below it — same policy the headless runner applies.
    for path_str in (str(root_path), str(entry_file.parent)):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    source = entry_file.read_text(encoding="utf-8")
    return spec_from_source(source, filename=str(entry_file), name=name)


def spec_from_source(
    source: str,
    *,
    filename: str = "<tempest-app>",
    name: str = "_tempest_app",
) -> AppSpec:
    """Compile app source and extract its :class:`AppSpec`.

    Shared by the file loader (above) and the dev server's code-push client,
    which receives source over the network rather than from disk.

    Args:
        source: The app module's Python source.
        filename: A label for tracebacks (a path or a synthetic name).
        name: The throwaway module name registered in ``sys.modules``.

    Returns:
        The loaded :class:`AppSpec`.

    Raises:
        AttributeError: If the source lacks ``view`` or ``make_state``.
        TypeError: If ``view`` or ``make_state`` is not callable.
    """
    # Compile and exec the source directly (no importlib / no .pyc cache) so a
    # reload always sees the latest edit, even within one mtime tick.
    module = ModuleType(name)
    module.__file__ = filename
    # Register before exec so decorators that resolve `sys.modules[__module__]`
    # (e.g. @dataclass) work. Reloads overwrite the same name on purpose.
    sys.modules[name] = module
    exec(compile(source, filename, "exec"), module.__dict__)  # noqa: S102

    if not hasattr(module, "view"):
        raise AttributeError(f"{filename} must define a `view(app)` function")
    if not hasattr(module, "make_state"):
        raise AttributeError(f"{filename} must define a `make_state()` factory")
    view = module.__dict__["view"]
    make_state = module.__dict__["make_state"]
    if not callable(view):
        raise TypeError(f"{filename}: `view` must be callable")
    if not callable(make_state):
        raise TypeError(f"{filename}: `make_state` must be callable")
    return AppSpec(
        make_state=cast("Callable[[], Any]", make_state),
        view=cast("Callable[[App[Any]], Widget]", view),
    )
