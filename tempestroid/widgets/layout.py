"""Layout widgets: ``Column``, ``Row`` and ``Container``."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tempestroid.widgets.base import Widget

__all__ = ["Column", "Row", "Container", "ScrollView"]


def _empty_children() -> list[Widget]:
    """Provide a fresh, typed empty child list for default factories.

    Returns:
        A new empty list of widgets.
    """
    return []


class Column(Widget):
    """A vertical flex container (main axis = top-to-bottom).

    Attributes:
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(default_factory=_empty_children)

    def child_nodes(self) -> list[Widget]:
        """Return the column's children.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Row(Widget):
    """A horizontal flex container (main axis = left-to-right).

    Attributes:
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(default_factory=_empty_children)

    def child_nodes(self) -> list[Widget]:
        """Return the row's children.

        Returns:
            The ordered child widgets.
        """
        return self.children


class Container(Widget):
    """A single-child box used for padding, background, borders and sizing.

    Attributes:
        child: The optional wrapped widget.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"child"})
    child: Widget | None = None

    def child_nodes(self) -> list[Widget]:
        """Return the wrapped child, if any.

        Returns:
            A one-element list with the child, or an empty list.
        """
        return [self.child] if self.child is not None else []


class ScrollView(Widget):
    """A scrollable container holding an overflowing list of children.

    Attributes:
        horizontal: When ``True``, children lay out and scroll left-to-right;
            otherwise they stack and scroll top-to-bottom.
        children: The ordered child widgets.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    horizontal: bool = False
    children: list[Widget] = Field(default_factory=_empty_children)

    def child_nodes(self) -> list[Widget]:
        """Return the scroll view's children.

        Returns:
            The ordered child widgets.
        """
        return self.children
