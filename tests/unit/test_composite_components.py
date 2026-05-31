"""Tests for the composite components (``AppBar``/``Header``/``Footer``/
``Sidebar``/``Scaffold``/``NavBar``) and the ``Component`` expansion in ``build``.

Components must lower to primitive widgets via ``Component.render`` *before* the
IR is built, so neither renderer ever sees a component node.
"""

from __future__ import annotations

import pytest

from tempestroid import (
    AppBar,
    Avatar,
    Burger,
    Button,
    Calendar,
    Card,
    Clock,
    Color,
    Column,
    Component,
    Divider,
    Drawer,
    Footer,
    Header,
    ListTile,
    NavBar,
    Node,
    Scaffold,
    Sidebar,
    Style,
    Text,
    Update,
    build,
    diff,
    merge_style,
    serialize_node,
)

_COMPOSITE_TYPES = frozenset(
    {
        "Component",
        "AppBar",
        "Header",
        "Footer",
        "Sidebar",
        "Scaffold",
        "NavBar",
        "Burger",
        "Drawer",
        "Calendar",
        "Clock",
        "Card",
        "ListTile",
        "Avatar",
        "Divider",
    }
)


def _walk(node: Node) -> list[Node]:
    """Return ``node`` and all its descendants in pre-order."""
    out = [node]
    for child in node.children:
        out.extend(_walk(child))
    return out


# --- Component base ---------------------------------------------------------


def test_component_base_render_is_abstract() -> None:
    class Bare(Component):
        pass

    with pytest.raises(NotImplementedError):
        build(Bare())


def test_build_expands_component_to_primitives() -> None:
    types = {n.type for n in _walk(build(AppBar(title="Hi")))}
    assert not (types & _COMPOSITE_TYPES)
    assert "Row" in types and "Text" in types


def test_nested_components_expand_recursively() -> None:
    tree = Scaffold(
        app_bar=AppBar(title="T"),
        body=Column(children=[Header(title="H", subtitle="s")]),
        bottom_bar=NavBar(items=["a"], active=0, on_select=lambda _i: None),
    )
    types = {n.type for n in _walk(build(tree))}
    assert not (types & _COMPOSITE_TYPES), types
    assert serialize_node(build(tree))  # lowers to a JSON-able primitive tree


# --- AppBar / Header / Footer ----------------------------------------------


def test_appbar_orders_leading_title_actions() -> None:
    node = build(
        AppBar(
            title="Title",
            leading=Button(label="menu", key="lead"),
            actions=[Button(label="x", key="act")],
        )
    )
    assert node.type == "Row"
    labels = [n.props.get("content") for n in _walk(node) if n.type == "Text"]
    assert "Title" in labels
    keys = [n.key for n in _walk(node)]
    assert (
        keys.index("lead")
        < keys.index("appbar-title")
        < keys.index("appbar-actions")
    )


def test_header_subtitle_optional() -> None:
    def texts(node: Node) -> list[Node]:
        return [n for n in _walk(node) if n.type == "Text"]

    assert len(texts(build(Header(title="t", subtitle="s")))) == 2
    assert len(texts(build(Header(title="t")))) == 1


def test_footer_holds_children() -> None:
    node = build(Footer(children=[Text(content="©", key="c")]))
    assert node.type == "Row"
    assert any(n.key == "c" for n in _walk(node))


# --- Sidebar / Scaffold -----------------------------------------------------


def test_sidebar_sets_fixed_width() -> None:
    node = build(Sidebar(children=[Text(content="x")], width=300.0))
    assert node.type == "Column"
    assert node.props["style"].width == 300.0


def test_scaffold_stacks_bars_and_body_in_order() -> None:
    node = build(
        Scaffold(
            app_bar=AppBar(title="bar"),
            body=Text(content="body"),
            bottom_bar=Footer(children=[]),
        )
    )
    assert node.type == "Column"
    top_keys = [child.key for child in node.children]
    assert top_keys == ["appbar", "scaffold-body", "footer"]


def test_scaffold_defaults_to_empty_body() -> None:
    node = build(Scaffold())
    assert node.type == "Column"
    assert [c.key for c in node.children] == ["scaffold-body"]


# --- NavBar -----------------------------------------------------------------


def test_navbar_highlights_active_item() -> None:
    node = build(NavBar(items=["a", "b", "c"], active=1, on_select=lambda _i: None))
    buttons = [n for n in _walk(node) if n.type == "Button"]
    assert len(buttons) == 3
    backgrounds = [b.props["style"].background for b in buttons]
    # exactly one (the active) differs from the rest
    assert backgrounds[1] != backgrounds[0]
    assert backgrounds[0] == backgrounds[2]


def test_navbar_on_select_receives_index() -> None:
    seen: list[int] = []
    node = build(NavBar(items=["a", "b"], active=0, on_select=seen.append))
    buttons = [n for n in _walk(node) if n.type == "Button"]
    buttons[1].props["on_click"]()
    assert seen == [1]


def test_navbar_self_diff_is_update_only() -> None:
    def make() -> NavBar:
        return NavBar(items=["a", "b"], active=0, on_select=lambda _i: None)

    patches = diff(build(make()), build(make()))
    # fresh handler identities read as prop changes (documented A2/A4 limit),
    # but the structure is stable: no Replace/Insert/Remove.
    assert patches
    assert all(isinstance(p, Update) for p in patches)


# --- merge_style ------------------------------------------------------------


def test_merge_style_override_wins_defaults_kept() -> None:
    base = Style(gap=12.0, background=Color.from_hex("#111111"))
    merged = merge_style(base, Style(background=Color.from_hex("#222222")))
    assert merged.gap == 12.0
    assert merged.background == Color.from_hex("#222222")


def test_merge_style_none_returns_base_unchanged() -> None:
    base = Style(gap=4.0)
    assert merge_style(base, None) is base


def test_component_style_overrides_default() -> None:
    node = build(AppBar(title="t", style=Style(background=Color.from_hex("#abcdef"))))
    assert node.props["style"].background == Color.from_hex("#abcdef")


# --- Burger / Drawer --------------------------------------------------------


def test_burger_renders_button_and_fires() -> None:
    fired: list[bool] = []
    node = build(Burger(on_click=lambda: fired.append(True)))
    assert node.type == "Button"
    node.props["on_click"]()
    assert fired == [True]


def test_drawer_collapses_when_closed() -> None:
    closed = build(Drawer(open=False, children=[Text(content="x")]))
    assert closed.type == "Container"
    assert closed.children == []


def test_drawer_shows_children_when_open() -> None:
    opened = build(Drawer(open=True, children=[Text(content="x", key="x")]))
    assert opened.type == "Column"
    assert any(n.key == "x" for n in _walk(opened))
    assert opened.props["style"].width == 260.0


# --- Calendar ---------------------------------------------------------------


def test_calendar_lays_out_every_day_of_month() -> None:
    node = build(Calendar(month="2026-05", selected="", on_select=lambda _d: None))
    days = {n.props["label"] for n in _walk(node) if n.type == "Button"}
    assert days == {str(d) for d in range(1, 32)}  # May has 31 days


def test_calendar_on_select_emits_iso_date() -> None:
    seen: list[str] = []
    node = build(Calendar(month="2026-05", selected="", on_select=seen.append))
    day15 = next(
        n for n in _walk(node) if n.type == "Button" and n.props["label"] == "15"
    )
    day15.props["on_click"]()
    assert seen == ["2026-05-15"]


def test_calendar_highlights_selected_day() -> None:
    node = build(
        Calendar(month="2026-05", selected="2026-05-31", on_select=lambda _d: None)
    )
    buttons = {
        n.props["label"]: n.props["style"].background
        for n in _walk(node)
        if n.type == "Button"
    }
    assert buttons["31"] != buttons["15"]


# --- Clock / Card / ListTile / Avatar / Divider -----------------------------


def test_clock_shows_time_and_optional_label() -> None:
    def texts(node: Node) -> list[Node]:
        return [n for n in _walk(node) if n.type == "Text"]

    assert len(texts(build(Clock(time="12:00", label="UTC")))) == 2
    without = texts(build(Clock(time="12:00")))
    assert len(without) == 1
    assert without[0].props["content"] == "12:00"


def test_card_wraps_children_in_elevated_container() -> None:
    node = build(Card(children=[Text(content="body", key="b")]))
    assert node.type == "Container"
    assert node.props["style"].shadow is not None
    assert any(n.key == "b" for n in _walk(node))


def test_listtile_orders_leading_text_trailing() -> None:
    node = build(
        ListTile(
            title="T",
            subtitle="s",
            leading=Avatar(initials="MB", key="lead"),
            trailing=Button(label="go", key="trail"),
        )
    )
    assert node.type == "Row"
    keys = [n.key for n in _walk(node)]
    assert keys.index("lead") < keys.index("tile-text") < keys.index("trail")


def test_avatar_is_circular_with_initials() -> None:
    node = build(Avatar(initials="MB", size=48.0))
    assert node.type == "Container"
    assert node.props["style"].radius == 24.0
    assert any(n.props.get("content") == "MB" for n in _walk(node))


def test_divider_is_a_thin_line() -> None:
    node = build(Divider(thickness=2.0))
    assert node.type == "Container"
    assert node.props["style"].height == 2.0
    assert node.children == []
