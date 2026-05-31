"""Scaffold a new tempestroid app (phase C, ``tempest new``).

Writes a minimal, runnable app that satisfies the ``make_state()`` + ``view(app)``
contract — it runs in the Qt simulator (``tempest dev``) and on a device
(``tempest serve`` / ``build`` / ``run``) unchanged.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["scaffold_app", "APP_TEMPLATE"]

APP_TEMPLATE = """\
\"\"\"{name} — a tempestroid app.

Run in the desktop simulator:   uv run tempest dev {dirname}/app.py
Push to a connected device:     uv run tempest serve {dirname}/app.py
\"\"\"

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import App, Button, Color, Column, Edge, Style, Text, Widget


@dataclass
class State:
    \"\"\"The app state.\"\"\"

    count: int = 0


def make_state() -> State:
    \"\"\"Build a fresh initial state.\"\"\"
    return State()


def _increment(state: State) -> None:
    \"\"\"Bump the counter.\"\"\"
    state.count += 1


def view(app: App[State]) -> Widget:
    \"\"\"Build the UI for the current state.\"\"\"
    return Column(
        style=Style(
            padding=Edge.all(24),
            gap=16,
            background=Color(r=245, g=245, b=250),
        ),
        children=[
            Text(
                content=f"{name}: {{app.state.count}}",
                style=Style(font_size=28, color=Color(r=20, g=20, b=40)),
            ),
            Button(label="tap me", on_click=lambda: app.set_state(_increment)),
        ],
    )
"""


def scaffold_app(target: Path, *, name: str | None = None) -> Path:
    """Create a new app directory with a runnable ``app.py``.

    Args:
        target: The directory to create (must not already contain ``app.py``).
        name: Display name embedded in the template; defaults to the dir name.

    Returns:
        The path to the written ``app.py``.

    Raises:
        FileExistsError: If ``target/app.py`` already exists.
    """
    target = Path(target)
    app_file = target / "app.py"
    if app_file.exists():
        raise FileExistsError(f"{app_file} already exists")
    target.mkdir(parents=True, exist_ok=True)
    display = name or target.name or "tempestroid app"
    app_file.write_text(
        APP_TEMPLATE.format(name=display, dirname=target.name or "app"),
        encoding="utf-8",
    )
    return app_file
