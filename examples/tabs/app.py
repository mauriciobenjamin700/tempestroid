"""Tabbed navigation — gallery example (device-ready).

A persistent tab bar swaps the body between three panels while shared state
survives the switch. This is the canonical *navigation* pattern: the body is a
single child that the reconciler ``Replace``s when the active tab changes, so it
shows how view switching lowers to patches. It deliberately sticks to the widget
set the device (Compose) renderer already handles — ``Text`` / ``Button`` /
``Column`` / ``Row`` / ``Container`` / ``Input`` / ``Checkbox`` — so it renders
the same in the Qt simulator and on a real device.

Runs in the Qt simulator::

    uv run python examples/tabs/app.py
    uv run tempest dev examples/tabs/app.py     # + hot restart on save

and on a device via code-push::

    uv run tempest serve examples/tabs/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Button,
    Checkbox,
    Color,
    Column,
    Container,
    Edge,
    FontWeight,
    Input,
    JustifyContent,
    Row,
    Style,
    Text,
    TextChangeEvent,
    ToggleEvent,
    Widget,
)

_TABS: tuple[str, ...] = ("Home", "Profile", "Settings")

_BG = Color.from_hex("#0b0f14")
_SURFACE = Color.from_hex("#1f2937")
_ACCENT = Color.from_hex("#2563eb")
_MUTED = Color.from_hex("#374151")
_TEXT = Color.from_hex("#f9fafb")
_SUBTLE = Color.from_hex("#9ca3af")


@dataclass
class TabsState:
    """The navigation demo's mutable state.

    Attributes:
        active: The index of the currently selected tab.
        name: The name typed on the Profile tab (persists across switches).
        notifications: Whether the Settings notification toggle is on.
        taps: How many times the Home action button has been pressed.
    """

    active: int = 0
    name: str = ""
    notifications: bool = True
    taps: int = 0


def make_state() -> TabsState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new navigation state on the Home tab.
    """
    return TabsState()


def _tab_button(app: App[TabsState], index: int, label: str) -> Widget:
    """Build one tab-bar button.

    Args:
        app: The running app.
        index: The tab index this button selects.
        label: The button's visible label.

    Returns:
        A button styled as active or inactive for the current tab.
    """
    active = app.state.active == index
    return Button(
        label=label,
        on_click=lambda: app.set_state(lambda s: setattr(s, "active", index)),
        key=f"tab-{index}",
        style=Style(
            grow=1.0,
            padding=Edge.symmetric(vertical=12.0, horizontal=8.0),
            radius=10.0,
            background=_ACCENT if active else _MUTED,
            color=_TEXT,
            font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
        ),
    )


def _card(*, title: str, children: list[Widget], key: str) -> Widget:
    """Wrap panel content in a titled surface card.

    Args:
        title: The card heading.
        children: The widgets stacked under the heading.
        key: The reconciler key for the card.

    Returns:
        A container framing the titled content.
    """
    return Container(
        key=key,
        style=Style(
            padding=Edge.all(20.0),
            radius=14.0,
            background=_SURFACE,
        ),
        child=Column(
            style=Style(gap=14.0),
            children=[
                Text(
                    content=title,
                    style=Style(
                        font_size=20.0,
                        font_weight=FontWeight.BOLD,
                        color=_TEXT,
                    ),
                ),
                *children,
            ],
        ),
    )


def _home_panel(app: App[TabsState]) -> Widget:
    """Build the Home tab body.

    Args:
        app: The running app.

    Returns:
        The Home panel card.
    """
    return _card(
        title="Home",
        key="panel-home",
        children=[
            Text(
                content=f"Action pressed {app.state.taps} time(s).",
                style=Style(color=_SUBTLE, font_size=15.0),
            ),
            Button(
                label="Do the thing",
                on_click=lambda: app.set_state(
                    lambda s: setattr(s, "taps", s.taps + 1)
                ),
                key="home-action",
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=18.0),
                    radius=10.0,
                    background=_ACCENT,
                    color=_TEXT,
                ),
            ),
        ],
    )


def _profile_panel(app: App[TabsState]) -> Widget:
    """Build the Profile tab body.

    Args:
        app: The running app.

    Returns:
        The Profile panel card.
    """
    name = app.state.name.strip()
    return _card(
        title="Profile",
        key="panel-profile",
        children=[
            Text(
                content=f"Hello, {name}!" if name else "Tell me your name:",
                style=Style(color=_TEXT, font_size=16.0),
            ),
            Input(
                value=app.state.name,
                placeholder="Your name",
                on_change=lambda e: _set_name(app, e),
                key="profile-name",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
                    radius=8.0,
                    background=_BG,
                    color=_TEXT,
                ),
            ),
        ],
    )


def _settings_panel(app: App[TabsState]) -> Widget:
    """Build the Settings tab body.

    Args:
        app: The running app.

    Returns:
        The Settings panel card.
    """
    enabled = app.state.notifications
    return _card(
        title="Settings",
        key="panel-settings",
        children=[
            Checkbox(
                label="Push notifications",
                checked=enabled,
                on_change=lambda e: _set_notifications(app, e),
                key="settings-notify",
            ),
            Text(
                content=(
                    "Notifications are on." if enabled else "Notifications are off."
                ),
                style=Style(color=_SUBTLE, font_size=14.0),
            ),
        ],
    )


def _set_name(app: App[TabsState], event: TextChangeEvent) -> None:
    """Fold a name-field edit back into state.

    Args:
        app: The running app.
        event: The validated text-change event.
    """
    app.set_state(lambda s: setattr(s, "name", event.value))


def _set_notifications(app: App[TabsState], event: ToggleEvent) -> None:
    """Fold the notification toggle back into state.

    Args:
        app: The running app.
        event: The validated toggle event.
    """
    app.set_state(lambda s: setattr(s, "notifications", event.checked))


_PANELS = (_home_panel, _profile_panel, _settings_panel)


def view(app: App[TabsState]) -> Widget:
    """Build the tabbed UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the navigation screen.
    """
    body = _PANELS[app.state.active](app)
    return Column(
        style=Style(
            gap=16.0,
            padding=Edge.all(20.0),
            background=_BG,
        ),
        children=[
            Text(
                content="tempestroid",
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=_TEXT,
                ),
                key="brand",
            ),
            Row(
                style=Style(gap=8.0, justify=JustifyContent.CENTER),
                children=[
                    _tab_button(app, index, label) for index, label in enumerate(_TABS)
                ],
                key="tabbar",
            ),
            # Single body child → switching tabs emits a Replace patch.
            Column(
                style=Style(align=AlignItems.STRETCH),
                children=[body],
                key="body",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — tabs", size=(380, 520))
    )
