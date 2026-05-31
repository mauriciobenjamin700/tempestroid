"""App shell — gallery example built from the composite components.

Assembles a full screen from :mod:`tempestroid.components` and exercises the whole
set: a ``Scaffold`` frames an ``AppBar`` (with a ``Burger`` toggling a ``Drawer``)
on top and a ``NavBar`` at the bottom; the body swaps per the active tab. The
Library tab uses ``Card`` / ``ListTile`` / ``Avatar`` / ``Divider``; the Profile
tab uses ``Clock`` and ``Calendar``. It is the component-driven version of the
``tabs`` example — far less hand-wiring — and uses only the Compose-supported
widget set, so it renders the same in the simulator and on a device.

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
    Avatar,
    Burger,
    Calendar,
    Card,
    Clock,
    Column,
    Container,
    Divider,
    Drawer,
    Edge,
    Header,
    ListTile,
    NavBar,
    Row,
    Scaffold,
    Style,
    Widget,
)

_TABS: tuple[str, ...] = ("Home", "Library", "Profile")


@dataclass
class ShellState:
    """The shell's mutable state.

    Attributes:
        active: The index of the selected bottom-navigation tab.
        drawer_open: Whether the side drawer is expanded.
        selected_date: The day picked on the Profile calendar (ISO, or empty).
    """

    active: int = 0
    drawer_open: bool = False
    selected_date: str = ""


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
            Clock(time="09:41", label="Local time"),
        ],
        key="home",
    )


def _library(_app: App[ShellState]) -> Widget:
    """Build the Library tab body.

    Args:
        _app: The running app (unused).

    Returns:
        The Library section as a card of list tiles.
    """
    people = (("Ana Lima", "Online"), ("Beto Reis", "Away"), ("Caio Souza", "Offline"))
    tiles: list[Widget] = []
    for index, (name, status) in enumerate(people):
        if index:
            tiles.append(Divider(key=f"div-{index}"))
        initials = "".join(part[0] for part in name.split()[:2])
        tiles.append(
            ListTile(
                title=name,
                subtitle=status,
                leading=Avatar(initials=initials, key=f"av-{index}"),
                key=f"tile-{index}",
            )
        )
    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            Header(title="Library", subtitle="Your contacts"),
            Card(children=tiles, key="contacts"),
        ],
        key="library",
    )


def _profile(app: App[ShellState]) -> Widget:
    """Build the Profile tab body.

    Args:
        app: The running app.

    Returns:
        The Profile section with a calendar bound to state.
    """

    def pick(iso: str) -> None:
        app.set_state(lambda s: setattr(s, "selected_date", iso))

    chosen = app.state.selected_date or "none"
    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            Header(title="Profile", subtitle=f"Picked: {chosen}"),
            Calendar(
                month="2026-05",
                selected=app.state.selected_date,
                on_select=pick,
                key="cal",
            ),
        ],
        key="profile",
    )


_BODIES = (_home, _library, _profile)


def _drawer(app: App[ShellState]) -> Widget:
    """Build the navigation drawer (a quick-jump list of the tabs).

    Args:
        app: The running app.

    Returns:
        A ``Drawer`` controlled by ``state.drawer_open``.
    """

    def go(index: int) -> None:
        def mutate(s: ShellState) -> None:
            s.active = index
            s.drawer_open = False

        app.set_state(mutate)

    return Drawer(
        open=app.state.drawer_open,
        width=200.0,
        children=[
            NavBar(
                items=list(_TABS),
                active=app.state.active,
                on_select=go,
                key="drawer-nav",
                style=Style(gap=8.0),
            )
        ],
        key="drawer",
    )


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

    def toggle_drawer() -> None:
        app.set_state(lambda s: setattr(s, "drawer_open", not s.drawer_open))

    body = Row(
        style=Style(grow=1.0, gap=0.0),
        children=[
            _drawer(app),
            Container(style=Style(grow=1.0), child=_BODIES[app.state.active](app)),
        ],
        key="body-row",
    )
    return Scaffold(
        app_bar=AppBar(
            title="tempestroid",
            leading=Burger(on_click=toggle_drawer),
        ),
        body=body,
        bottom_bar=NavBar(items=list(_TABS), active=app.state.active, on_select=select),
    )


def main() -> int:
    """Run the shell in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — shell", size=(420, 640))


if __name__ == "__main__":
    raise SystemExit(main())
