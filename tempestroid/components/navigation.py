"""Navigation components: ``NavBar`` (a.k.a. tab bar).

``NavBar`` generalises the ``examples/tabs`` pattern into a reusable component:
a row of selectable items with a highlighted active index. Because a
:class:`Component`'s :meth:`render` runs wherever ``build`` runs (desktop *and*
device), the per-item handlers can close over the caller's ``on_select`` and the
item index directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestroid.components.base import ACCENT, MUTED, ON_SURFACE, SURFACE, merge_style
from tempestroid.style import Edge, FontWeight, JustifyContent, Style
from tempestroid.widgets import Button, Component, Row, Widget

__all__ = ["NavBar"]


def _no_labels() -> list[str]:
    """Provide a fresh, typed empty label list for the default factory.

    Returns:
        A new empty list of strings.
    """
    return []


class NavBar(Component):
    """A horizontal navigation/tab bar with a highlighted active item.

    Attributes:
        items: The visible item labels, in order.
        active: The index of the currently selected item.
        on_select: Called with the tapped item's index when an item is pressed.
    """

    items: list[str] = Field(default_factory=_no_labels)
    active: int = 0
    on_select: Callable[[int], Any]

    def _make_handler(self, index: int) -> Callable[[], None]:
        """Build a zero-argument handler that selects ``index``.

        Args:
            index: The item index this handler selects.

        Returns:
            A click handler invoking ``on_select`` with ``index``.
        """

        def handler() -> None:
            self.on_select(index)

        return handler

    def _item(self, index: int, label: str) -> Widget:
        """Build one navigation item button.

        Args:
            index: The item's position in the bar.
            label: The item's visible label.

        Returns:
            A button styled as active or inactive for ``self.active``.
        """
        active = index == self.active
        return Button(
            label=label,
            on_click=self._make_handler(index),
            key=f"nav-{index}",
            style=Style(
                grow=1.0,
                padding=Edge.symmetric(vertical=12.0, horizontal=8.0),
                radius=10.0,
                background=ACCENT if active else MUTED,
                color=ON_SURFACE,
                font_weight=FontWeight.BOLD if active else FontWeight.NORMAL,
            ),
        )

    def render(self) -> Widget:
        """Lower the navigation bar into a primitive row of buttons.

        Returns:
            A ``Row`` of item buttons with the active one highlighted.
        """
        default = Style(
            gap=8.0,
            padding=Edge.all(8.0),
            justify=JustifyContent.CENTER,
            background=SURFACE,
        )
        return Row(
            key=self.key or "navbar",
            style=merge_style(default, self.style),
            children=[
                self._item(index, label) for index, label in enumerate(self.items)
            ],
        )
