"""Scaffold a new tempestroid app project (``tempest new``).

Writes a fully configured, runnable project: an ``app.py`` honoring the
framework's ``make_state`` + ``view`` contract, a ``pyproject.toml`` declaring
the ``tempestroid[qt]`` dependency and the ``[tool.tempest] app`` pointer (so
``tempest dev``/``serve``/``build`` run with no app argument inside the
project), a ``README.md`` with the dev-loop commands, and a ``.gitignore``.

``tempest new .`` scaffolds **in place** into the current directory (the project
name is taken from the directory name); ``tempest new <name>`` creates a new
subdirectory. The template is pure Python — no Qt import at module level — so the
same file targets the desktop simulator and the Android device.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempestroid.cli.templates import TEMPLATES, py_safe, render_files

__all__ = ["scaffold", "DEFAULT_APP_TEMPLATE", "ScaffoldResult", "template_names"]


def template_names() -> list[str]:
    """List the available ``tempest new`` template names.

    Returns:
        ``["default", ...]`` — the built-in single-file template plus every
        multi-file template in :data:`tempestroid.cli.templates.TEMPLATES`.
    """
    return ["default", *TEMPLATES.keys()]

DEFAULT_APP_TEMPLATE = """\
\"\"\"{name} — a tempestroid app.

Run it in the Qt simulator with hot reload::

    uv run tempest dev

Push it to a device over LAN (no APK rebuild)::

    uv run tempest serve

Both commands read the app path from ``[tool.tempest] app`` in pyproject.toml.
The contract every tempestroid app honors: a ``make_state()`` factory and a
``view(app)`` builder. Keep this module free of Qt imports so it runs on both
the desktop simulator and the Android device.
\"\"\"

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)


@dataclass
class State:
    \"\"\"The app's mutable state.

    Attributes:
        value: The current counter value.
    \"\"\"

    value: int = 0


def make_state() -> State:
    \"\"\"Build a fresh initial state (used on every hot restart).

    Returns:
        A new state at zero.
    \"\"\"
    return State()


def view(app: App[State]) -> Widget:
    \"\"\"Build the UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget.
    \"\"\"
    return Column(
        style=Style(
            align=AlignItems.CENTER,
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#101418"),
        ),
        children=[
            Text(
                content=f"{name}: {{app.state.value}}",
                style=Style(
                    color=Color.from_hex("#ffffff"),
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="label",
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(
                        label="-",
                        on_click=lambda: app.set_state(
                            lambda s: setattr(s, "value", s.value - 1)
                        ),
                        key="dec",
                    ),
                    Button(
                        label="+",
                        on_click=lambda: app.set_state(
                            lambda s: setattr(s, "value", s.value + 1)
                        ),
                        key="inc",
                    ),
                ],
            ),
        ],
    )
"""

PYPROJECT_TEMPLATE = """\
[project]
name = "{project}"
version = "0.1.0"
description = "A tempestroid app — native Android in typed Python."
requires-python = ">=3.11"
dependencies = ["tempestroid[qt]>=0.2"]

# `tempest dev`/`serve`/`build`/`run` read this when no app path is given, so
# inside the project you can run `tempest dev` with no arguments.
[tool.tempest]
app = "app.py"
"""

README_TEMPLATE = """\
# {name}

A [tempestroid](https://pypi.org/project/tempestroid/) app — native Android in
typed Python.

## Setup

```bash
uv sync                                 # install tempestroid + the Qt simulator
```

## Develop

```bash
uv run tempest dev                      # Qt simulator + hot reload (edit & save)
```

In the `tempest dev` cockpit: `r` hot-reloads (state preserved), `R` restarts
clean, `s` raises the window, `q` quits. (`tempest dev`/`serve`/`build` read the
app path from `[tool.tempest] app` in `pyproject.toml`.)

## Run on a device (the easy path — no Android SDK/NDK, no download)

The host APK ships inside `tempestroid`, so installing is offline and instant:

```bash
uv run tempest install                  # adb-install the bundled host APK
uv run tempest serve                    # push over LAN + auto-launch in dev mode
```

`tempest serve` pushes app code to the installed host and edit-and-save
hot-reloads on the device — no Gradle build or toolchain needed.

## Build an APK from source (advanced — needs Android SDK/NDK)

```bash
uv run tempest build                    # package an APK from source
uv run tempest run                      # build + install on a device + logs
```
"""

GITIGNORE_TEMPLATE = """\
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/

# tempestroid / tooling
.ruff_cache/
.pytest_cache/
"""

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_PROJECT_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


class ScaffoldResult:
    """The outcome of a scaffold operation.

    Attributes:
        root: The project directory that was written to.
        name: The human-facing project name.
        in_place: ``True`` when scaffolded into an existing directory (``.``).
    """

    def __init__(self, root: Path, name: str, *, in_place: bool) -> None:
        """Initialize the result.

        Args:
            root: The project directory.
            name: The project name.
            in_place: Whether the scaffold was in-place.
        """
        self.root: Path = root
        self.name: str = name
        self.in_place: bool = in_place


def _project_slug(name: str) -> str:
    """Derive a valid project (distribution) name from a directory name.

    Args:
        name: A raw directory name.

    Returns:
        A lowercase, hyphen-normalized slug usable as a ``[project] name``.
    """
    slug = _PROJECT_SANITIZE_RE.sub("-", name.lower()).strip("-._")
    return slug or "app"


def scaffold(
    name: str, *, parent: str | Path = ".", template: str = "default"
) -> ScaffoldResult:
    """Create a fully configured app project from a template.

    ``name == "."`` scaffolds in place into ``parent`` (the current directory by
    default), taking the project name from the directory; any other ``name``
    creates a new subdirectory under ``parent``.

    All templates share the common project files (``pyproject.toml`` with the
    ``[tool.tempest] app`` pointer, ``README.md``, ``.gitignore``); the chosen
    template supplies the app modules. ``default`` writes a single ``app.py``;
    the multi-file templates (see :data:`tempestroid.cli.templates.TEMPLATES`)
    write a ``state.py`` + ``screens/`` + ``components/`` tree.

    Args:
        name: The project/directory name, or ``"."`` to scaffold in place. A
            named project must start with a letter and contain only letters,
            digits, ``-`` or ``_``.
        parent: Directory to create the project under (default: cwd).
        template: The template name (``"default"`` or a key of
            :data:`tempestroid.cli.templates.TEMPLATES`).

    Returns:
        A :class:`ScaffoldResult` describing what was written.

    Raises:
        ValueError: If a named ``name`` is not a valid project/identifier name,
            or ``template`` is unknown.
        FileExistsError: If the target directory exists (named) or already holds
            an ``app.py`` (in place).
    """
    if template != "default" and template not in TEMPLATES:
        known = ", ".join(template_names())
        raise ValueError(f"unknown template {template!r}; choose one of: {known}")

    in_place = name in (".", "./")
    if in_place:
        root = Path(parent).resolve()
        display = root.name or "app"
        root.mkdir(parents=True, exist_ok=True)
        if (root / "app.py").exists():
            raise FileExistsError(f"app.py already exists in {root}")
    else:
        if not _NAME_RE.match(name):
            raise ValueError(
                f"invalid project name {name!r}: start with a letter; use only "
                "letters, digits, hyphen or underscore (or a dot for in place)"
            )
        display = name
        root = Path(parent).resolve() / name
        if root.exists():
            raise FileExistsError(f"directory already exists: {root}")
        root.mkdir(parents=True)

    project = _project_slug(display)
    if template == "default":
        # Escape the name for the generated .py (docstring + f-string + title);
        # an in-place scaffold's directory name is otherwise unconstrained.
        (root / "app.py").write_text(
            DEFAULT_APP_TEMPLATE.format(name=py_safe(display)), encoding="utf-8"
        )
    else:
        for rel_path, content in render_files(TEMPLATES[template], display).items():
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        PYPROJECT_TEMPLATE.format(project=project), encoding="utf-8"
    )
    (root / "README.md").write_text(
        README_TEMPLATE.format(name=display), encoding="utf-8"
    )
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
    return ScaffoldResult(root, display, in_place=in_place)
