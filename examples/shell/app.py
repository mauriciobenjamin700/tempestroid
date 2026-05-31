"""App shell — gallery example built from the composite components.

Assembles a full screen from :mod:`tempestroid.components`: a ``Scaffold`` frames
an ``AppBar`` on top, a ``NavBar`` at the bottom and a body that swaps per the
active tab (with a ``Header`` per section). It is the component-driven version of
the ``tabs`` example — same navigation behaviour, far less hand-wiring — and uses
only the Compose-supported widget set, so it renders the same in the simulator
and on a device.

Runs in the Qt simulator::

    uv run python examples/shell/app.py
    uv run tempest dev examples/shell/app.py     # + hot restart on save

and on a device via code-push::

    uv run tempest serve examples/shell/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    App,
    AppBar,
    Button,
    Color,
    Column,
    Edge,
    Header,
    NavBar,
    Scaffold,
    Style,
    Text,
    Widget,
)

_TABS: tuple[str, ...] = ("Home", "Library", "Profile")


@dataclass
class ShellState:
    """The shell's mutable state.

    Attributes:
        active: The index of the selected bottom-navigation tab.
        plays: How many times the Home "Play" action has been pressed.
    """

    active: int = 0
    plays: int = 0


def make_state() -> ShellState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new shell state on the first tab.
    """
    return ShellState()


def _home(app: App[ShellState]) -> Widget:
    """Build the Home tab body.

    Args:
        app: The running app.

    Returns:
        The Home section content.
    """
    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            Header(title="Home", subtitle="What's new today"),
            Text(
                content=f"Played {app.state.plays} time(s).",
                style=Style(color=Color.from_hex("#9ca3af"), font_size=15.0),
            ),
            Button(
                label="Play",
                on_click=lambda: app.set_state(
                    lambda s: setattr(s, "plays", s.plays + 1)
                ),
                key="play",
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=18.0),
                    radius=10.0,
                    background=Color.from_hex("#2563eb"),
                    color=Color.from_hex("#ffffff"),
                ),
            ),
        ],
        key="home",
    )


def _library(_app: App[ShellState]) -> Widget:
    """Build the Library tab body.

    Args:
        _app: The running app (unused).

    Returns:
        The Library section content.
    """
    return Column(
        style=Style(gap=8.0, padding=Edge.all(20.0)),
        children=[
            Header(title="Library", subtitle="Your saved items"),
            *[
                Text(
                    content=f"• Item {n}",
                    style=Style(color=Color.from_hex("#e5e7eb"), font_size=16.0),
                    key=f"item-{n}",
                )
                for n in range(1, 5)
            ],
        ],
        key="library",
    )


def _profile(_app: App[ShellState]) -> Widget:
    """Build the Profile tab body.

    Args:
        _app: The running app (unused).

    Returns:
        The Profile section content.
    """
    return Column(
        style=Style(gap=8.0, padding=Edge.all(20.0)),
        children=[
            Header(title="Profile", subtitle="mauricio@example.com"),
            Text(
                content="Signed in.",
                style=Style(color=Color.from_hex("#9ca3af"), font_size=15.0),
            ),
        ],
        key="profile",
    )


_BODIES = (_home, _library, _profile)


def view(app: App[ShellState]) -> Widget:
    """Build the shell UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the shell screen.
    """

    def select(index: int) -> None:
        app.set_state(lambda s: setattr(s, "active", index))

    return Scaffold(
        app_bar=AppBar(
            title="tempestroid",
            actions=[
                Button(
                    label="?",
                    key="help",
                    style=Style(
                        padding=Edge.symmetric(vertical=8.0, horizontal=12.0),
                        radius=8.0,
                        background=Color.from_hex("#374151"),
                        color=Color.from_hex("#f9fafb"),
                    ),
                )
            ],
        ),
        body=_BODIES[app.state.active](app),
        bottom_bar=NavBar(items=list(_TABS), active=app.state.active, on_select=select),
    )


def main() -> int:
    """Run the shell in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — shell", size=(380, 560))


if __name__ == "__main__":
    raise SystemExit(main())
