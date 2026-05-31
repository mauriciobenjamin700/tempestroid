"""Bar components: ``AppBar``, ``Header`` and ``Footer``.

Each is a :class:`Component` that lowers to a primitive ``Row``/``Column`` tree,
so they render identically in the Qt simulator and on the Compose device.
"""

from __future__ import annotations

from pydantic import Field

from tempestroid.components.base import (
    BACKGROUND,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestroid.style import AlignItems, Edge, FontWeight, Style
from tempestroid.widgets import Column, Component, Row, Text, Widget

__all__ = ["AppBar", "Header", "Footer"]


def _no_widgets() -> list[Widget]:
    """Provide a fresh, typed empty widget list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class AppBar(Component):
    """A top application bar: optional leading widget, title and trailing actions.

    Attributes:
        title: The bar's title text.
        leading: An optional widget shown before the title (e.g. a menu or back
            button); omitted when ``None``.
        actions: Trailing action widgets laid out at the end of the bar.
    """

    title: str = ""
    leading: Widget | None = None
    actions: list[Widget] = Field(default_factory=_no_widgets)

    def render(self) -> Widget:
        """Lower the app bar into a horizontal primitive row.

        Returns:
            A ``Row`` with the leading widget, a growing title and the actions.
        """
        children: list[Widget] = []
        if self.leading is not None:
            children.append(self.leading)
        children.append(
            Text(
                content=self.title,
                style=Style(
                    grow=1.0,
                    font_size=20.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="appbar-title",
            )
        )
        if self.actions:
            children.append(
                Row(style=Style(gap=8.0), children=self.actions, key="appbar-actions")
            )
        default = Style(
            padding=Edge.symmetric(vertical=14.0, horizontal=16.0),
            gap=12.0,
            align=AlignItems.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "appbar",
            style=merge_style(default, self.style),
            children=children,
        )


class Header(Component):
    """A page header band: a title with an optional subtitle.

    Attributes:
        title: The header's primary line.
        subtitle: An optional secondary line shown muted under the title.
    """

    title: str = ""
    subtitle: str | None = None

    def render(self) -> Widget:
        """Lower the header into a stacked primitive column.

        Returns:
            A ``Column`` with the title and, when set, the subtitle.
        """
        children: list[Widget] = [
            Text(
                content=self.title,
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                ),
                key="header-title",
            )
        ]
        if self.subtitle is not None:
            children.append(
                Text(
                    content=self.subtitle,
                    style=Style(font_size=14.0, color=ON_MUTED),
                    key="header-subtitle",
                )
            )
        default = Style(padding=Edge.all(20.0), gap=4.0, background=BACKGROUND)
        return Column(
            key=self.key or "header",
            style=merge_style(default, self.style),
            children=children,
        )


class Footer(Component):
    """A bottom bar holding arbitrary, centered content.

    Attributes:
        children: The widgets laid out in the footer (e.g. links or labels).
    """

    children: list[Widget] = Field(default_factory=_no_widgets)

    def render(self) -> Widget:
        """Lower the footer into a centered primitive row.

        Returns:
            A ``Row`` containing the footer's children.
        """
        default = Style(
            padding=Edge.symmetric(vertical=12.0, horizontal=16.0),
            gap=12.0,
            align=AlignItems.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "footer",
            style=merge_style(default, self.style),
            children=self.children,
        )
