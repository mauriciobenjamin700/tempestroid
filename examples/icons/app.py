"""Icon set + input icons + modern secure reveal — device verification app.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/icons/app.py

It exercises the curated icon set and the input icon slots:

* a row of :class:`~tempestroid.Icon` widgets rendered as vector glyphs from the
  built-in :class:`~tempestroid.Icons` set (search / user / mail / lock / star /
  trash);
* an :class:`~tempestroid.Input` with a ``leading_icon`` (search) and a
  ``trailing_icon`` (x);
* a ``secure`` password :class:`~tempestroid.Input` whose modern eye / eye-off
  reveal toggle flips masking locally, with a ``lock`` leading icon.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Color,
    Column,
    Edge,
    Icon,
    Icons,
    Input,
    Row,
    Style,
    Text,
    TextChangeEvent,
    Widget,
)


@dataclass
class State:
    """The app's mutable state.

    Attributes:
        query: The text typed into the searchable input.
        password: The text typed into the secure input.
    """

    query: str = ""
    password: str = ""


def make_state() -> State:
    """Build a fresh initial state.

    Returns:
        A new empty state.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Build the icon-showcase UI.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget.
    """
    gallery = [
        Icons.SEARCH,
        Icons.USER,
        Icons.MAIL,
        Icons.LOCK,
        Icons.STAR,
        Icons.TRASH,
    ]

    def on_query(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "query", event.value))

    def on_password(event: TextChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "password", event.value))

    return Column(
        style=Style(
            align=AlignItems.STRETCH,
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Icon set",
                style=Style(color=Color.from_hex("#ffffff"), font_size=20.0),
                key="title",
            ),
            Row(
                style=Style(gap=16.0),
                children=[
                    Icon(
                        name=name,
                        size=28.0,
                        style=Style(color=Color.from_hex("#9ca3af")),
                        key=f"icon-{name}",
                    )
                    for name in gallery
                ],
                key="gallery",
            ),
            Input(
                value=app.state.query,
                placeholder="Search…",
                leading_icon=Icons.SEARCH,
                trailing_icon=Icons.X,
                on_change=on_query,
                key="search",
            ),
            Input(
                value=app.state.password,
                placeholder="Password",
                secure=True,
                leading_icon=Icons.LOCK,
                on_change=on_password,
                key="password",
            ),
        ],
    )
