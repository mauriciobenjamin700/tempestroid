"""Qt-renderer tests for the navigation host widgets and Esc -> pop.

Exercises Navigator/TabView/TabBar/RouteDrawer under
``QT_QPA_PLATFORM=offscreen``: a Navigator hosts a QStackedWidget and a screen
swap (push/pop) applies a Replace without exceptions and keeps the new screen
visible; a TabBar tap dispatches a typed RouteChangeEvent; a RouteDrawer slides
its panel on ``open``; and Esc on the host routes to ``App.pop``.
"""

# This suite reaches into renderer internals (_NavHost / _TabBarWidget /
# _DrawerHost) to assert Qt geometry/state, and wires throwaway view + event
# lambdas over an untyped app; relax the matching strict rules here (the
# convention used by tests/unit/test_overlay_gestures.py).
# pyright: reportPrivateUsage=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QStackedWidget, QWidget

from tempestroid import (
    App,
    Navigator,
    Route,
    RouteChangeEvent,
    RouteDrawer,
    TabBar,
    TabView,
    Text,
    Widget,
)
from tempestroid.core.ir import Replace, Update
from tempestroid.core.reconciler import build, diff
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.app_runner import BackKeyFilter
from tempestroid.renderers.qt.renderer import _DrawerHost, _NavHost, _TabBarWidget

pytestmark = pytest.mark.usefixtures("qapp")


def _labels(widget: QWidget) -> list[str]:
    """Collect every visible QLabel text under a widget."""
    return [child.text() for child in widget.findChildren(QLabel)]


# --- IR-level diff contract (props + diffable child) -----------------------


def test_navigator_build_exposes_transition_prop_and_diffable_child() -> None:
    node = build(Navigator(child=Text(content="home"), transition="slide", depth=0))
    assert node.type == "Navigator"
    assert node.props["transition"] == "slide"
    assert node.props["depth"] == 0
    assert [c.type for c in node.children] == ["Text"]


def test_navigator_same_screen_type_diffs_to_update() -> None:
    old = build(Navigator(child=Text(content="a"), depth=0))
    new = build(Navigator(child=Text(content="b"), depth=1))
    patches = diff(old, new)
    # depth change on Navigator + content change on the child -> two Updates,
    # no new patch kind.
    assert all(isinstance(p, Update) for p in patches)
    updates = [p for p in patches if isinstance(p, Update)]
    assert any(p.set_props == {"content": "b"} for p in updates)


def test_navigator_different_screen_type_diffs_to_replace() -> None:
    from tempestroid import Button

    old = build(Navigator(child=Text(content="a"), depth=0))
    new = build(Navigator(child=Button(label="go"), depth=1))
    patches = diff(old, new)
    # the screen subtree changes type -> a Replace on the Navigator's child.
    assert any(isinstance(p, Replace) for p in patches)


# --- Qt rendering ----------------------------------------------------------


def _nav_app(view: Any) -> tuple[App[object], QtRenderer]:
    renderer = QtRenderer()
    app: App[object] = App(object(), view, apply_patches=renderer.apply)
    renderer.mount(app.start().root)
    return app, renderer


def test_navigator_hosts_a_qstacked_widget() -> None:
    _app, renderer = _nav_app(
        lambda app: Navigator(
            child=Text(content=app.nav.top.name), depth=len(app.nav.stack) - 1
        )
    )
    host = renderer.root_widget
    assert isinstance(host, _NavHost)
    assert host.findChild(QStackedWidget) is not None
    assert "/" in _labels(host)


async def test_push_then_pop_swaps_screen_without_exception() -> None:
    app, renderer = _nav_app(
        lambda app: Navigator(
            child=Text(content=app.nav.top.name), depth=len(app.nav.stack) - 1
        )
    )
    host = renderer.root_widget
    app.push(Route(name="/details"))
    await asyncio.sleep(0)  # flush the coalesced rebuild
    assert app.nav.top.name == "/details"
    assert "/details" in _labels(host)
    app.pop()
    await asyncio.sleep(0)
    assert app.nav.top.name == "/"
    assert "/" in _labels(host)


async def test_push_three_screens_keeps_stack_host_alive() -> None:
    app, renderer = _nav_app(
        lambda app: Navigator(
            child=Text(content=app.nav.top.name),
            depth=len(app.nav.stack) - 1,
            transition="none",
        )
    )
    host = renderer.root_widget
    for name in ("/a", "/b", "/c"):
        app.push(Route(name=name))
        await asyncio.sleep(0)
    assert "/c" in _labels(host)
    assert app.pop() is True
    await asyncio.sleep(0)
    assert "/b" in _labels(host)


# --- TabView / TabBar ------------------------------------------------------


def test_tab_bar_tap_dispatches_typed_route_change_event() -> None:
    received: list[RouteChangeEvent] = []
    renderer = QtRenderer()
    node = build(
        TabBar(tabs=["Home", "Settings"], active=0, on_change=received.append)
    )
    renderer.mount(node)
    bar = renderer.root_widget
    assert isinstance(bar, _TabBarWidget)
    bar._buttons[1].click()
    assert len(received) == 1
    assert isinstance(received[0], RouteChangeEvent)
    assert received[0].name == "Settings"
    assert received[0].params == {"index": 1}


async def test_tab_view_tap_switches_active_content() -> None:
    received: list[RouteChangeEvent] = []

    def view(app: App[Any]) -> Widget:
        active = app.state["active"]

        def on_change(event: RouteChangeEvent) -> None:
            received.append(event)
            app.set_state(lambda s: s.__setitem__("active", event.params["index"]))

        return TabView(
            tabs=["A", "B"],
            active=active,
            child=Text(content=f"tab{active}"),
            on_change=on_change,
        )

    renderer = QtRenderer()
    app: App[Any] = App({"active": 0}, view, apply_patches=renderer.apply)
    renderer.mount(app.start().root)
    host = renderer.root_widget
    assert isinstance(host, _NavHost)
    assert host.tab_bar is not None
    assert "tab0" in _labels(host)
    host.tab_bar._buttons[1].click()
    await asyncio.sleep(0)
    assert received[0].params == {"index": 1}
    assert app.state["active"] == 1
    assert "tab1" in _labels(host)


# --- RouteDrawer -----------------------------------------------------------


def test_route_drawer_renders_content_and_panel() -> None:
    renderer = QtRenderer()
    node = build(
        RouteDrawer(
            child=Text(content="main"),
            drawer=Text(content="panel"),
            open=False,
        )
    )
    host = renderer.mount(node)
    host.resize(400, 800)
    drawer_host = renderer.root_widget
    assert isinstance(drawer_host, _DrawerHost)
    labels = _labels(drawer_host)
    assert "main" in labels and "panel" in labels


async def test_route_drawer_open_change_slides_panel() -> None:
    def view(app: App[Any]) -> Widget:
        return RouteDrawer(
            child=Text(content="main"),
            drawer=Text(content="panel"),
            open=app.state["open"],
        )

    renderer = QtRenderer()
    app: App[Any] = App({"open": False}, view, apply_patches=renderer.apply)
    host = renderer.mount(app.start().root)
    host.resize(400, 800)
    drawer_host = renderer.root_widget
    assert isinstance(drawer_host, _DrawerHost)
    closed_x = drawer_host.drawer.x() if drawer_host.drawer is not None else 0
    app.set_state(lambda s: s.__setitem__("open", True))
    await asyncio.sleep(0)
    assert drawer_host._open is True
    # open target is left of the closed (off-screen) position
    open_target = drawer_host.width() - drawer_host._panel_width()
    assert open_target < closed_x


# --- Esc -> pop ------------------------------------------------------------


def _press_escape(target: QWidget) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )


async def test_escape_filter_pops_a_route() -> None:
    app, renderer = _nav_app(
        lambda app: Navigator(
            child=Text(content=app.nav.top.name), depth=len(app.nav.stack) - 1
        )
    )
    host = renderer.host
    filt = BackKeyFilter(lambda: app)
    host.installEventFilter(filt)
    app.push(Route(name="/a"))
    await asyncio.sleep(0)
    assert app.nav.top.name == "/a"
    consumed = filt.eventFilter(host, _press_escape(host))
    await asyncio.sleep(0)
    assert consumed is True
    assert app.nav.top.name == "/"


async def test_escape_filter_at_root_is_noop() -> None:
    app, renderer = _nav_app(
        lambda app: Navigator(
            child=Text(content=app.nav.top.name), depth=len(app.nav.stack) - 1
        )
    )
    filt = BackKeyFilter(lambda: app)
    consumed = filt.eventFilter(renderer.host, _press_escape(renderer.host))
    await asyncio.sleep(0)
    # Esc is swallowed but the stack is unchanged (pop at root is a no-op).
    assert consumed is True
    assert app.nav.top.name == "/"
    assert len(app.nav.stack) == 1
