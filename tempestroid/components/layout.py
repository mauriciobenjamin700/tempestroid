"""Page-structure components: ``Sidebar`` and ``Scaffold``.

``Sidebar`` is a fixed-width lateral column; ``Scaffold`` is the page frame that
stacks an app bar, a growing body and an optional bottom bar. Both lower to
primitive ``Column``/``Container`` trees.
"""

from __future__ import annotations

from pydantic import Field

from tempestroid.components.base import BACKGROUND, ON_SURFACE, SURFACE, merge_style
from tempestroid.style import Edge, Style
from tempestroid.widgets import Column, Component, Container, ScrollView, Widget

__all__ = ["Sidebar", "Scaffold"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Sidebar(Component):
    """A fixed-width lateral column of navigation/content widgets.

    Attributes:
        children: The widgets stacked top-to-bottom in the sidebar.
        width: The sidebar's fixed width in logical pixels.
    """

    children: list[Widget] = Field(default_factory=_no_widgets)
    width: float = 240.0

    def render(self) -> Widget:
        """Lower the sidebar into a fixed-width primitive column.

        Returns:
            A ``Column`` carrying the sidebar's children.
        """
        default = Style(
            width=self.width,
            padding=Edge.all(16.0),
            gap=10.0,
            background=SURFACE,
            color=ON_SURFACE,
        )
        return Column(
            key=self.key or "sidebar",
            style=merge_style(default, self.style),
            children=self.children,
        )


class Scaffold(Component):
    """A page frame: app bar on top, growing body, optional bottom bar.

    Attributes:
        app_bar: The top bar widget (commonly an :class:`AppBar`); omitted when
            ``None``.
        body: The main content; defaults to an empty column when ``None``.
        bottom_bar: A bottom bar widget (e.g. a :class:`NavBar` or ``Footer``);
            omitted when ``None``.
        scroll: When ``True``, the body is wrapped in a ``ScrollView`` (a Qt
            convenience; the Compose renderer scrolls natively post-Trilho-B).
    """

    app_bar: Widget | None = None
    body: Widget | None = None
    bottom_bar: Widget | None = None
    scroll: bool = False

    def render(self) -> Widget:
        """Lower the scaffold into a stacked primitive column.

        Returns:
            A ``Column`` stacking the app bar, the (growing) body and the bottom
            bar in order.
        """
        children: list[Widget] = []
        if self.app_bar is not None:
            children.append(self.app_bar)
        body: Widget = self.body if self.body is not None else Column()
        if self.scroll:
            body = ScrollView(
                children=[body], style=Style(grow=1.0), key="scaffold-body"
            )
        else:
            body = Container(child=body, style=Style(grow=1.0), key="scaffold-body")
        children.append(body)
        if self.bottom_bar is not None:
            children.append(self.bottom_bar)
        default = Style(gap=0.0, background=BACKGROUND)
        return Column(
            key=self.key or "scaffold",
            style=merge_style(default, self.style),
            children=children,
        )
