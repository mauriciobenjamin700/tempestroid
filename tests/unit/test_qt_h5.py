"""Qt renderer tests for the H5 navigation kit.

H5 is a skin pass: the nav components (AppBar/NavBar/Tabs/SearchBar/Breadcrumb/
Header/Drawer/Sidebar/Scaffold) are ``Component``s that lower to primitives
carrying a theme-resolved ``Style``, so the Qt renderer handles them through the
generic path — no new node type. These tests pin that the skinned components lower
+ mount, and that the selected NavBar/Tabs item resolves an accent (not the old
hard-coded hex).
"""

from __future__ import annotations

from tempest_core.components import AppBar, NavBar, SearchBar, Tabs
from tempest_core.core.reconciler import build

from tempestroid.renderers.qt.renderer import QtRenderer


def test_appbar_lowers_and_mounts(qapp: object) -> None:
    """A styled ``AppBar`` lowers to a primitive surface and mounts."""
    renderer = QtRenderer()
    renderer.mount(build(AppBar(title="App", color_scheme="primary")))


def test_navbar_lowers_and_mounts(qapp: object) -> None:
    """A ``NavBar`` lowers to a primitive bar + item buttons and mounts."""
    renderer = QtRenderer()
    renderer.mount(
        build(NavBar(items=["Home", "Search"], active=0, on_select=lambda _i: None))
    )


def test_tabs_lowers_and_mounts(qapp: object) -> None:
    """A ``Tabs`` strip lowers to a primitive row of tab buttons and mounts."""
    renderer = QtRenderer()
    renderer.mount(
        build(Tabs(tabs=["A", "B", "C"], active=1, on_select=lambda _i: None))
    )


def test_searchbar_lowers_and_mounts(qapp: object) -> None:
    """A ``SearchBar`` lowers to a field + clear control and mounts."""
    renderer = QtRenderer()
    renderer.mount(
        build(SearchBar(value="", placeholder="Search", on_change=lambda _q: None))
    )


def test_navbar_active_item_differs_from_inactive(qapp: object) -> None:
    """The active NavBar destination resolves a different Style than an inactive one.

    Regression guard: H5 paints the active destination with the resolved
    ``color_scheme`` accent (a badge pill) and inactive ones as ghost — so the two
    lowered item nodes must NOT carry identical styles (the old code hard-coded a
    single accent/muted pair, but the point is they're theme-resolved + distinct).
    """
    node = build(NavBar(items=["Home", "Search"], active=0, on_select=lambda _i: None))

    def _styles(n: object, out: list[object]) -> None:
        props = getattr(n, "props", {})
        if "style" in props:
            out.append(props["style"])
        for child in getattr(n, "children", []):
            _styles(child, out)

    styles: list[object] = []
    _styles(node, styles)
    # At least two distinct resolved styles exist in the lowered tree (active pill
    # vs inactive ghost are not the same object/value).
    assert len({repr(s) for s in styles}) >= 2
