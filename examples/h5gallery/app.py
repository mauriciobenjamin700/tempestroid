"""H5 design-system gallery — the styled navigation kit.

Showcases the Trilho H phase H5 components: ``AppBar``, ``Header``, ``Tabs``,
``NavBar``, ``SearchBar`` and ``Breadcrumb`` — each resolving its look from the
design-system ``Theme`` (M3 surfaces + the selected-item accent from
``color_scheme``), with no hand-set colors.

Run in the Qt simulator::

    uv run python examples/h5gallery/app.py

Renderer-agnostic — the Qt renderer is imported lazily inside ``main`` so the
device loader (no PySide6) can import this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    AppBar,
    Breadcrumb,
    Color,
    Column,
    Edge,
    FontWeight,
    Header,
    NavBar,
    SearchBar,
    Style,
    Tabs,
    Text,
    VStack,
    Widget,
)


@dataclass
class GalleryState:
    """The showcase's mutable state.

    Attributes:
        tab: The active tab index.
        nav: The active bottom-nav destination index.
        query: The current search text.
        tabs: The tab labels.
        nav_items: The bottom-nav destination labels.
    """

    tab: int = 0
    nav: int = 0
    query: str = ""
    tabs: list[str] = field(
        default_factory=lambda: ["Overview", "Activity", "Settings"]
    )
    nav_items: list[str] = field(
        default_factory=lambda: ["Home", "Search", "Profile"]
    )


def make_state() -> GalleryState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new gallery state.
    """
    return GalleryState()


def _heading(title: str, *, key: str) -> Widget:
    """Build a small uppercase section heading.

    Args:
        title: The heading text.
        key: The stable diff key.

    Returns:
        A muted, bold ``Text`` label.
    """
    return Text(
        content=title,
        style=Style(
            color=Color.from_hex("#6b7280"),
            font_size=12.0,
            font_weight=FontWeight.BOLD,
        ),
        key=key,
    )


def _section(title: str, *, key: str, body: Widget) -> Widget:
    """Build a titled section block.

    Args:
        title: The section heading.
        key: The stable diff key.
        body: The section content.

    Returns:
        A ``VStack`` with the heading above the body.
    """
    return VStack(gap="sm", key=key, children=[_heading(title, key="h"), body])


def view(app: App[GalleryState]) -> Widget:
    """Build the H5 gallery tree.

    Args:
        app: The application whose state drives the showcase.

    Returns:
        The root widget for the current state.
    """
    s = app.state

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        key="root",
        children=[
            _section(
                "APP BAR (elevated surface)",
                key="sec-appbar",
                body=AppBar(
                    title="Tempestroid",
                    color_scheme="primary",
                    key="appbar",
                ),
            ),
            _section(
                "HEADER",
                key="sec-header",
                body=Header(
                    title="Painel",
                    subtitle="Visão geral do projeto",
                    key="header",
                ),
            ),
            _section(
                "BREADCRUMB",
                key="sec-crumb",
                body=Breadcrumb(
                    items=["Início", "Projetos", "Tempestroid"],
                    on_select=lambda _i: None,
                    key="crumb",
                ),
            ),
            _section(
                "SEARCH BAR",
                key="sec-search",
                body=SearchBar(
                    value=s.query,
                    placeholder="Buscar…",
                    on_change=lambda q: app.set_state(
                        lambda st: GalleryState(
                            tab=st.tab, nav=st.nav, query=q,
                            tabs=st.tabs, nav_items=st.nav_items,
                        )
                    ),
                    color_scheme="primary",
                    key="search",
                ),
            ),
            _section(
                "TABS (selected accent + underline)",
                key="sec-tabs",
                body=Tabs(
                    tabs=s.tabs,
                    active=s.tab,
                    on_select=lambda i: app.set_state(
                        lambda st: GalleryState(
                            tab=i, nav=st.nav, query=st.query,
                            tabs=st.tabs, nav_items=st.nav_items,
                        )
                    ),
                    color_scheme="primary",
                    key="tabs",
                ),
            ),
            _section(
                "NAV BAR (active destination pill)",
                key="sec-nav",
                body=NavBar(
                    items=s.nav_items,
                    active=s.nav,
                    on_select=lambda i: app.set_state(
                        lambda st: GalleryState(
                            tab=st.tab, nav=i, query=st.query,
                            tabs=st.tabs, nav_items=st.nav_items,
                        )
                    ),
                    color_scheme="primary",
                    key="nav",
                ),
            ),
        ],
    )


def main() -> None:
    """Run the gallery in the Qt simulator (lazy import keeps the module clean)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(view, make_state())


if __name__ == "__main__":
    main()
