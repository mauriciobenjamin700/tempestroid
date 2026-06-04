"""Headless Qt-renderer tests for the E9 cross-cutting surface.

Covers the device-independent half of E9c: accessibility (`Semantics` ->
`QAccessible` name/description + focus policy from `focusable`) and the dark/light
theme palette swap (`App.theme` -> `QApplication` palette via `sync_context`). The
on-device proof (TalkBack reading labels, the dark snapshot on the phone) stays a
hardware-gated follow-up.
"""

# pyright: reportPrivateUsage=false
from dataclasses import dataclass

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from tempestroid import (
    App,
    Semantics,
    Text,
    Theme,
    ThemeMode,
    Widget,
    build,
)
from tempestroid.renderers.qt.renderer import QtRenderer

pytestmark = pytest.mark.usefixtures("qapp")


@dataclass
class _State:
    """Empty state for the theme harness."""


def _view(_app: App[_State]) -> Widget:
    """Trivial view used only to wire an App to the renderer."""
    return Text(content="x")


def test_semantics_set_accessible_name_description_and_focus_policy():
    # A widget's Semantics maps to QAccessible name/description, and focusable
    # drives the Qt focus policy — the device-independent half of a11y.
    renderer = QtRenderer()
    renderer.mount(
        build(
            Text(
                content="Hello",
                semantics=Semantics(label="Greeting", hint="say hi", role="heading"),
                focusable=True,
            )
        )
    )
    widget = renderer.root_widget
    assert widget is not None
    assert widget.accessibleName() == "Greeting"
    assert widget.accessibleDescription() == "say hi"
    assert widget.focusPolicy() != widget.focusPolicy().NoFocus


def test_theme_dark_swaps_the_application_palette():
    # Switching App.theme to dark and re-syncing applies the dark QPalette to the
    # QApplication (the Qt simulator's theme mechanism; Compose uses MaterialTheme).
    app: App[_State] = App(_State(), _view, lambda _patches: None)
    renderer = QtRenderer()
    renderer.set_app(app)
    renderer.mount(build(_view(app)))

    app.theme = Theme(mode=ThemeMode.DARK)
    renderer.sync_context()

    qapp = QApplication.instance()
    assert isinstance(qapp, QApplication)
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(30, 30, 30)

    app.theme = Theme(mode=ThemeMode.LIGHT)
    renderer.sync_context()
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor(245, 245, 245)
