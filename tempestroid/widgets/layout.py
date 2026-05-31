"""Layout widgets: ``Column``, ``Row``, ``Container``, ``ScrollView`` and ``Stack``."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tempestroid.widgets.base import Widget

__all__ = ["Column", "Row", "Container", "ScrollView", "Stack"]


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


class Stack(Widget):
    """An overlapping container: children share one box, layered by z-order.

    Unlike ``Column``/``Row`` (which lay children out along an axis), a ``Stack``
    paints its children on top of one another in declaration order — the first
    child is the bottom layer, the last is on top. This is the framework's
    overlay primitive: a scrim, a modal card, a toast or a floating action button
    is just a later child of a ``Stack`` wrapping the page content.

    Non-positioned children are aligned within the box by the stack's
    :attr:`~tempestroid.style.Style.stack_align`. A child whose style sets
    ``position = ABSOLUTE`` is anchored instead by its
    ``top``/``right``/``bottom``/``left`` insets (Flutter ``Positioned`` / CSS
    ``position: absolute``); set both ``left`` and ``right`` (or ``top`` and
    ``bottom``) to stretch it across that axis — a full-bleed scrim is
    ``position = ABSOLUTE`` with all four insets at ``0``.

    Attributes:
        children: The ordered child widgets, bottom layer first.
    """

    child_field_names: ClassVar[frozenset[str]] = frozenset({"children"})
    children: list[Widget] = Field(default_factory=_empty_children)

    def child_nodes(self) -> list[Widget]:
        """Return the stack's children in z-order (bottom layer first).

        Returns:
            The ordered child widgets.
        """
        return self.children
