"""Composite, higher-level UI components built from primitive widgets.

Each component is a :class:`tempestroid.widgets.Component` that lowers to a
primitive ``Text`` / ``Row`` / ``Column`` / ``Container`` tree via its ``render``
method, so it works in both renderers (Qt and Compose) with no renderer changes
and is fully device-ready. The package collects reusable page-structure and
navigation building blocks:

* :class:`AppBar` — top bar with leading widget, title and trailing actions.
* :class:`Header` / :class:`Footer` — page header band and bottom bar.
* :class:`Sidebar` — fixed-width lateral column.
* :class:`Scaffold` — page frame stacking app bar, body and bottom bar.
* :class:`NavBar` — selectable navigation/tab bar with an active index.

The default theme tokens and :func:`merge_style` (used to overlay a caller's
``style`` onto a component default) are re-exported for building custom
components in the same idiom.
"""

from __future__ import annotations

from tempestroid.components.bars import AppBar, Footer, Header
from tempestroid.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestroid.components.cards import Avatar, Card, Divider, ListTile
from tempestroid.components.dates import Calendar, Clock
from tempestroid.components.layout import Scaffold, Sidebar
from tempestroid.components.menu import Burger, Drawer
from tempestroid.components.navigation import NavBar

__all__ = [
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
    "merge_style",
    "BACKGROUND",
    "SURFACE",
    "ACCENT",
    "MUTED",
    "ON_SURFACE",
    "ON_MUTED",
]
