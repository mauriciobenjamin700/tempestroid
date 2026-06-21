"""Unit tests for navigation: the route stack and the App navigation helpers."""

import asyncio
from dataclasses import dataclass

import pytest
from pydantic import ValidationError
from tempest_core.core.introspection import event_catalog, introspect

from tempestroid import (
    App,
    Navigator,
    NavStack,
    Route,
    RouteChangeEvent,
    RouteDrawer,
    TabBar,
    TabView,
    Text,
    Update,
    Widget,
    parse_event,
    routes_from_path,
)
from tempestroid.bridge import BACK_TOKEN, DeviceApp, LoopbackBridge, make_event_sink


@dataclass
class State:
    """Minimal app state for navigation tests."""

    value: int = 0


def _view(app: "App[State]") -> Widget:
    """Build a screen labelled by the active route name."""
    return Text(content=app.nav.top.name)


def _make_app() -> tuple["App[State]", list[list[object]]]:
    """Create an app capturing every applied patch batch."""
    captured: list[list[object]] = []
    app: App[State] = App(
        State(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    return app, captured


def test_route_is_frozen_and_keeps_params():
    route = Route(name="/details", params={"id": 7})
    assert route.name == "/details"
    assert route.params == {"id": 7}
    with pytest.raises(ValidationError):
        route.name = "/other"  # type: ignore[misc]


def test_route_default_params_is_empty_dict():
    route = Route(name="/")
    assert route.params == {}


def test_navstack_defaults_to_root():
    nav = NavStack()
    assert len(nav.stack) == 1
    assert nav.top.name == "/"
    assert nav.can_pop is False


def test_navstack_top_and_can_pop():
    nav = NavStack(stack=[Route(name="/"), Route(name="/a")])
    assert nav.top.name == "/a"
    assert nav.can_pop is True


def test_app_has_default_navstack():
    app, _ = _make_app()
    assert isinstance(app.nav, NavStack)
    assert app.nav.top.name == "/"


def test_app_accepts_custom_navstack():
    nav = NavStack(stack=[Route(name="/"), Route(name="/seed")])
    app: App[State] = App(State(), _view, apply_patches=lambda _p: None, nav=nav)
    assert app.nav.top.name == "/seed"


async def test_push_appends_and_rebuilds():
    app, captured = _make_app()
    app.push(Route(name="/a"))
    await asyncio.sleep(0)
    assert app.nav.top.name == "/a"
    assert len(captured) == 1
    patch = captured[0][0]
    # the view rebuilds the same Text type, so the route change diffs to an Update
    assert isinstance(patch, Update)
    assert patch.set_props == {"content": "/a"}


async def test_multiple_push_in_one_tick_coalesce():
    app, captured = _make_app()
    app.push(Route(name="/a"))
    app.push(Route(name="/b"))
    app.push(Route(name="/c"))
    await asyncio.sleep(0)
    # three pushes, one coalesced rebuild reflecting the final route
    assert len(captured) == 1
    assert app.nav.top.name == "/c"
    assert [r.name for r in app.nav.stack] == ["/", "/a", "/b", "/c"]


async def test_pop_returns_to_previous():
    app, captured = _make_app()
    app.push(Route(name="/a"))
    await asyncio.sleep(0)
    captured.clear()
    assert app.pop() is True
    await asyncio.sleep(0)
    assert app.nav.top.name == "/"
    assert len(captured) == 1


async def test_pop_at_root_returns_false_and_keeps_stack():
    app, captured = _make_app()
    captured.clear()
    assert app.pop() is False
    await asyncio.sleep(0)
    assert app.nav.top.name == "/"
    assert len(app.nav.stack) == 1
    # no-op pop schedules no rebuild
    assert captured == []


async def test_replace_swaps_top_without_depth_change():
    app, _ = _make_app()
    app.push(Route(name="/a"))
    await asyncio.sleep(0)
    app.replace(Route(name="/b", params={"k": 1}))
    await asyncio.sleep(0)
    assert app.nav.top.name == "/b"
    assert app.nav.top.params == {"k": 1}
    assert [r.name for r in app.nav.stack] == ["/", "/b"]


async def test_reset_replaces_whole_stack():
    app, _ = _make_app()
    app.push(Route(name="/a"))
    await asyncio.sleep(0)
    app.reset([Route(name="/x"), Route(name="/y")])
    await asyncio.sleep(0)
    assert [r.name for r in app.nav.stack] == ["/x", "/y"]
    assert app.nav.top.name == "/y"


def test_reset_rejects_empty_stack():
    app, _ = _make_app()
    with pytest.raises(ValueError):
        app.reset([])


def test_route_change_event_validates_via_parse_event():
    event = parse_event(RouteChangeEvent, {"name": "/details", "params": {"id": 7}})
    assert isinstance(event, RouteChangeEvent)
    assert event.name == "/details"
    assert event.params == {"id": 7}


def test_route_change_event_is_frozen():
    event = RouteChangeEvent(name="/a")
    assert event.params == {}
    with pytest.raises(ValidationError):
        event.name = "/b"  # type: ignore[misc]


def test_route_change_event_in_introspection():
    assert "RouteChangeEvent" in event_catalog()
    assert "RouteChangeEvent" in introspect()["events"]


# --- navigation-widget IR surface (the contract E0c/Compose must mirror) ----


def test_nav_widgets_are_re_exported_from_package():
    # the four host widgets are importable at the package level (re-export gate)
    assert Navigator.__name__ == "Navigator"
    assert TabView.__name__ == "TabView"
    assert TabBar.__name__ == "TabBar"
    assert RouteDrawer.__name__ == "RouteDrawer"


def test_navigator_child_slot_and_props():
    nav = Navigator(child=Text(content="home"))
    assert nav.transition == "slide"  # default animation hint
    assert nav.depth == 0
    assert Navigator.child_field_names == frozenset({"child"})
    assert nav.child_nodes() == [nav.child]


def test_tab_bar_is_a_leaf_with_route_change_schema():
    bar = TabBar(tabs=["A", "B"])
    assert bar.active == 0
    assert bar.on_change is None
    # leaf: no child slots
    assert TabBar.child_field_names == frozenset()
    assert bar.child_nodes() == []
    assert TabBar.event_schemas == {"on_change": RouteChangeEvent}


def test_tab_view_child_slot_and_route_change_schema():
    view = TabView(tabs=["A", "B"], child=Text(content="tab0"))
    assert view.active == 0
    assert TabView.child_field_names == frozenset({"child"})
    assert view.child_nodes() == [view.child]
    assert TabView.event_schemas == {"on_change": RouteChangeEvent}


def test_route_drawer_two_child_slots_in_order():
    drawer = RouteDrawer(child=Text(content="main"), drawer=Text(content="panel"))
    assert drawer.open is False
    assert RouteDrawer.child_field_names == frozenset({"child", "drawer"})
    # child first, drawer second — order is the renderer/diff contract
    assert drawer.child_nodes() == [drawer.child, drawer.drawer]
    assert RouteDrawer.event_schemas == {"on_change": RouteChangeEvent}


def test_nav_widgets_appear_in_introspection_catalog():
    # `tempest spec` must list the four host widgets (done-when gate).
    widgets = introspect()["widgets"]
    for name in ("Navigator", "TabView", "TabBar", "RouteDrawer"):
        assert name in widgets, f"{name} missing from the introspection catalog"


# --- E0d: system back (__back__ token) over the device bridge ----------------


def _stack_view(app: "App[State]") -> Widget:
    """Build a screen labelled by the active route name (device-bridge tests)."""
    return Text(content=app.nav.top.name)


def test_back_token_is_reserved_and_exported():
    # The reserved back token carries no payload separator and re-exports cleanly.
    assert BACK_TOKEN == "__back__"
    import tempestroid

    assert tempestroid.BACK_TOKEN == "__back__"


def test_mount_message_reflects_can_pop_on_the_stack():
    # The host reads can_pop from the mount/patch envelope to gate its back button.
    bridge = LoopbackBridge()
    nav = NavStack(stack=[Route(name="/"), Route(name="/a")])
    device: DeviceApp[State] = DeviceApp(State(), _stack_view, bridge)
    device.app.nav.stack = nav.stack
    asyncio.run(device.start())
    assert bridge.sent[0]["kind"] == "mount"
    assert bridge.sent[0]["can_pop"] is True


def test_mount_message_can_pop_false_at_root():
    bridge = LoopbackBridge()
    device: DeviceApp[State] = DeviceApp(State(), _stack_view, bridge)
    asyncio.run(device.start())
    assert bridge.sent[0]["can_pop"] is False


async def test_back_token_pops_the_stack_via_event_sink():
    # A __back__ event off the device sink pops one screen and emits a patch
    # whose envelope reports the new (now poppable-or-not) stack depth.
    bridge = LoopbackBridge()
    device: DeviceApp[State] = DeviceApp(State(), _stack_view, bridge)
    device.app.nav.stack = [Route(name="/"), Route(name="/a"), Route(name="/b")]
    await device.start()
    assert bridge.sent[0]["can_pop"] is True

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(BACK_TOKEN, "")
    # the sink schedules the pop via call_soon_threadsafe; let the loop run the
    # pop, the coalesced rebuild it triggers, and the async patch send task.
    for _ in range(4):
        await asyncio.sleep(0)

    assert [r.name for r in device.app.nav.stack] == ["/", "/a"]
    patch_msg = bridge.sent[-1]
    assert patch_msg["kind"] == "patch"
    assert patch_msg["can_pop"] is True


async def test_back_token_at_root_is_a_noop():
    # At the root the back token is a no-op: the stack is untouched and no patch
    # is emitted (the host's default back action — closing the app — runs).
    bridge = LoopbackBridge()
    device: DeviceApp[State] = DeviceApp(State(), _stack_view, bridge)
    await device.start()
    assert len(bridge.sent) == 1

    loop = asyncio.get_running_loop()
    sink = make_event_sink(loop, device)
    sink(BACK_TOKEN, "")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(device.app.nav.stack) == 1
    assert len(bridge.sent) == 1  # no patch emitted by a no-op pop


@pytest.mark.parametrize("widget_type", ["TabView", "TabBar", "RouteDrawer"])
def test_navigation_widgets_registered_in_bridge_event_schemas(widget_type: str):
    # Regression: the bridge's EVENT_SCHEMAS must cover the navigation widgets so
    # the device path builds a typed RouteChangeEvent for their on_change handler.
    # Omitting them made event_type_for return None on device, so the bridge called
    # the tab/drawer handler with no args (TypeError) — a device-only break the Qt
    # path masked because it builds the event in renderer.py instead.
    from tempestroid.bridge.protocol import event_type_for

    assert event_type_for(widget_type, "on_change") is RouteChangeEvent


# --- E0d: deep link → reset(initial stack) -----------------------------------


def test_routes_from_path_root_is_single_route():
    routes = routes_from_path("/")
    assert [r.name for r in routes] == ["/"]


def test_routes_from_path_empty_is_single_route():
    routes = routes_from_path("")
    assert [r.name for r in routes] == ["/"]


def test_routes_from_path_builds_cumulative_back_stack():
    routes = routes_from_path("/shop/item")
    assert [r.name for r in routes] == ["/", "/shop", "/shop/item"]


def test_routes_from_path_single_segment():
    routes = routes_from_path("/details")
    assert [r.name for r in routes] == ["/", "/details"]


async def test_deep_link_resets_the_stack_via_reset():
    # The deep-link path: resolve a path to a stack and reset onto it. The app
    # opens directly on the linked screen with the intermediate back stack built.
    app, captured = _make_app()
    captured.clear()
    app.reset(routes_from_path("/shop/item"))
    await asyncio.sleep(0)
    assert [r.name for r in app.nav.stack] == ["/", "/shop", "/shop/item"]
    assert app.nav.top.name == "/shop/item"
    assert app.nav.can_pop is True
    assert len(captured) == 1
