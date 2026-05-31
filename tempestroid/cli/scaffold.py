"""Scaffold a new tempestroid app project (``tempest new``).

Writes a minimal, runnable project: an ``app.py`` honoring the framework's
``make_state`` + ``view`` contract (so it runs in the Qt simulator, ships over
``tempest serve``, and packages with ``tempest build`` unchanged), plus a
``README.md`` with the dev-loop commands. The template is pure Python — no Qt
import at module level — so the same file targets desktop and device.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["scaffold", "DEFAULT_APP_TEMPLATE"]

DEFAULT_APP_TEMPLATE = """\
\"\"\"{name} — a tempestroid app.

Run it in the Qt simulator with hot reload::

    uv run tempest dev {dirname}/app.py

Push it to a device over LAN (no APK rebuild)::

    uv run tempest serve {dirname}/app.py

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

README_TEMPLATE = """\
# {name}

A [tempestroid](https://pypi.org/project/tempestroid/) app — native Android in
typed Python.

## Develop

```bash
uv run tempest dev {dirname}/app.py     # Qt simulator + hot reload (edit & save)
uv run tempest serve {dirname}/app.py   # push to a device over LAN, no APK rebuild
```

In the `tempest dev` cockpit: `r` hot-reloads (state preserved), `R` restarts
clean, `s` raises the window, `q` quits.

## Build & run on a device

```bash
uv run tempest build {dirname}/app.py   # package a release APK
uv run tempest run {dirname}/app.py     # install on a connected device + stream logs
```
"""

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def scaffold(name: str, *, parent: str | Path = ".") -> Path:
    """Create a new app project directory from the default template.

    Args:
        name: The project name; also the directory name. Must start with a
            letter and contain only letters, digits, ``-`` or ``_``.
        parent: Directory to create the project under (default: cwd).

    Returns:
        The path to the created project directory.

    Raises:
        ValueError: If ``name`` is not a valid project/identifier name.
        FileExistsError: If the target directory already exists.
    """
    if not _NAME_RE.match(name):
        raise ValueError(
            f"invalid project name {name!r}: start with a letter; use only "
            "letters, digits, hyphen or underscore"
        )
    root = Path(parent).resolve() / name
    if root.exists():
        raise FileExistsError(f"directory already exists: {root}")
    root.mkdir(parents=True)
    rendered_app = DEFAULT_APP_TEMPLATE.format(name=name, dirname=name)
    (root / "app.py").write_text(rendered_app, encoding="utf-8")
    (root / "README.md").write_text(
        README_TEMPLATE.format(name=name, dirname=name), encoding="utf-8"
    )
    return root
