"""Navigation hosts demo — Navigator + TabView + RouteDrawer (device-ready).

Exercises the three navigation-host widgets that lower to native containers:

- :class:`~tempestroid.Navigator` — a push/pop stack of three screens, animated
  (slide forward on push, back on pop) by the renderer from the ``depth`` delta.
- :class:`~tempestroid.TabView` — a tab strip that swaps the body on tap.
- :class:`~tempestroid.RouteDrawer` — a side panel toggled open/closed.

It renders the same in the Qt simulator and on a real device (Compose), so it is
the dual-renderer proof for phase E0.

Runs in the Qt simulator::

    uv run python examples/navigation/app.py
    uv run tempest dev examples/navigation/app.py

and on a device via code-push::

    uv run tempest serve examples/navigation/app.py
"""

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
    JustifyContent,
    Navigator,
    Route,
    RouteChangeEvent,
    RouteDrawer,
    Style,
    TabView,
    Text,
    Widget,
)

_BG = Color.from_hex("#0b0f14")
_SURFACE = Color.from_hex("#1f2937")
_ACCENT = Color.from_hex("#2563eb")
_TEXT = Color.from_hex("#f9fafb")
_SUBTLE = Color.from_hex("#9ca3af")

_TABS: tuple[str, ...] = ("Stack", "Tabs", "Drawer")


@dataclass
class NavState:
    """Mutable state for the navigation demo.

    The inner Navigator stack depth is **not** stored here: it lives in
    ``app.nav`` (the framework's navigation stack), so the system back button can
    pop it (E0d). Only tab selection and the drawer toggle are app state.

    Attributes:
        active: The selected top-level tab index.
        drawer_open: Whether the RouteDrawer panel is open.
    """

    active: int = 0
    drawer_open: bool = False


def make_state() -> NavState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new navigation state on the Stack tab.
    """
    return NavState()


def _screen(title: str, body: Widget) -> Widget:
    """Build a full-bleed screen with a title and a body.

    Args:
        title: The screen title.
        body: The screen body widget.

    Returns:
        A styled column screen.
    """
    return Column(
        style=Style(
            background=_BG,
            padding=Edge.all(24),
            gap=16,
            justify=JustifyContent.START,
            align=AlignItems.STRETCH,
            grow=1,
        ),
        children=[
            Text(
                content=title,
                style=Style(color=_TEXT, font_size=24, font_weight=FontWeight.BOLD),
            ),
            body,
        ],
    )


def _stack_screen(app: App[NavState]) -> Widget:
    """Build the Navigator stack tab: real ``app.nav`` push/pop across screens.

    This drives the framework's own navigation stack (``app.nav``), so the
    device's system back button (E0d: the reserved ``__back__`` token routed to
    :meth:`~tempestroid.App.pop`) and the Qt simulator's Esc both pop a screen.
    The screen depth is read from ``len(app.nav.stack)`` rather than mirrored in
    ``S`` — the stack is the single source of truth.

    Args:
        app: The running app (read ``app.nav``, wire handlers).

    Returns:
        A Navigator wrapping the current stack screen.
    """
    depth = len(app.nav.stack)

    actions = Column(
        style=Style(gap=12, align=AlignItems.STRETCH),
        children=[
            Text(content=f"Screen {depth}", style=Style(color=_SUBTLE, font_size=16)),
            Text(
                content=f"route: {app.nav.top.name}",
                style=Style(color=_SUBTLE, font_size=14),
            ),
            Button(
                label="Push next screen",
                key="push",
                on_click=lambda: app.push(Route(name=f"/stack/{depth}")),
                style=Style(
                    background=_ACCENT,
                    color=_TEXT,
                    padding=Edge.symmetric(vertical=12, horizontal=20),
                    radius=10,
                ),
            ),
            Button(
                label="Pop back (or use system back)",
                key="pop",
                on_click=app.pop,
                style=Style(
                    background=_SURFACE,
                    color=_TEXT,
                    padding=Edge.symmetric(vertical=12, horizontal=20),
                    radius=10,
                ),
            ),
        ],
    )
    top = _screen(f"Stack — Screen {depth}", actions)
    # A distinct key per stack depth so the renderer animates the swap.
    top = top.model_copy(update={"key": f"stack-{depth}"})
    return Navigator(child=top, transition="slide", depth=depth)


def _tabs_screen(app: App[NavState]) -> Widget:
    """Build the inner TabView tab content.

    Args:
        app: The running app.

    Returns:
        A simple labelled body for the tab demo.
    """
    return _screen(
        "Tabs",
        Text(
            content="Tap the tab strip at the top to switch sections.",
            style=Style(color=_SUBTLE, font_size=16),
        ),
    )


def _drawer_screen(app: App[NavState]) -> Widget:
    """Build the RouteDrawer tab: a toggle button plus a side panel.

    Args:
        app: The running app.

    Returns:
        A RouteDrawer with content and a drawer panel.
    """
    state = app.state

    def open_drawer() -> None:
        state.drawer_open = True
        app.set_state()

    def on_drawer_change(event: RouteChangeEvent) -> None:
        state.drawer_open = bool(event.params.get("open", False))
        app.set_state()

    content = _screen(
        "Drawer",
        Button(
            label="Open drawer",
            on_click=open_drawer,
            style=Style(
                background=_ACCENT,
                color=_TEXT,
                padding=Edge.symmetric(vertical=12, horizontal=20),
                radius=10,
            ),
        ),
    )
    panel = Column(
        style=Style(background=_SURFACE, padding=Edge.all(24), gap=12, grow=1),
        children=[
            Text(
                content="Side panel",
                style=Style(color=_TEXT, font_size=20, font_weight=FontWeight.BOLD),
            ),
            Text(
                content="Tap outside to close.",
                style=Style(color=_SUBTLE, font_size=15),
            ),
        ],
    )
    return RouteDrawer(
        child=content,
        drawer=panel,
        open=state.drawer_open,
        on_change=on_drawer_change,
    )


def view(app: App[NavState]) -> Widget:
    """Build the top-level TabView switching between the three host demos.

    Args:
        app: The running app (read ``app.state``, wire handlers).

    Returns:
        The root widget tree.
    """
    state = app.state

    def on_tab(event: RouteChangeEvent) -> None:
        index = int(event.params.get("index", 0))
        state.active = index
        app.set_state()

    bodies = (_stack_screen, _tabs_screen, _drawer_screen)
    body = bodies[state.active](app)

    # Pad the top so the tab strip clears the status bar and stays tappable on
    # device (SafeArea would collapse a `grow` child, so use explicit padding).
    return TabView(
        tabs=list(_TABS),
        active=state.active,
        on_change=on_tab,
        child=body,
        style=Style(background=_BG, grow=1, padding=Edge(top=48)),
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    run_qt(view, make_state)
