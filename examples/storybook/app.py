"""Trilho H storybook — the whole design system in one navigable app.

A Storybook-style gallery: an ``AppBar`` with light/dark + LTR/RTL toggles, a
``Tabs`` strip switching between component categories (Action, Inputs, Surfaces,
Feedback, Navigation, Research), and a representative specimen of each H1–H6
component — all themed from ``app.theme`` so the dark/RTL toggles re-skin the
entire system live.

Run in the Qt simulator::

    uv run python examples/storybook/app.py

Renderer-agnostic — the Qt renderer is imported lazily inside ``main``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tempestroid import (
    Alert,
    AlertVariant,
    App,
    AppBar,
    BarChart,
    Button,
    Card,
    CardVariant,
    Checkbox,
    Chip,
    Column,
    ConfidenceBadge,
    DetectionBox,
    DetectionOverlay,
    Divider,
    Edge,
    HStack,
    IconButton,
    Input,
    Locale,
    MetricCard,
    NavBar,
    ProgressBar,
    Row,
    ScrollView,
    Size,
    Slider,
    Style,
    Surface,
    Switch,
    Tabs,
    Text,
    Theme,
    ThemeMode,
    Variant,
    VStack,
    Widget,
)

_CATEGORIES = [
    "Action",
    "Inputs",
    "Surfaces",
    "Feedback",
    "Navigation",
    "Research",
]


@dataclass
class StoryState:
    """The storybook's mutable state.

    Attributes:
        tab: The active category tab index.
    """

    tab: int = 0


def make_state() -> StoryState:
    """Build a fresh initial state.

    Returns:
        A new storybook state on the first category.
    """
    return StoryState()


def _action(theme: Theme) -> Widget:
    """Build the Action category specimens (buttons, icon buttons).

    Args:
        theme: The active design-system theme.

    Returns:
        A column of action-component specimens.
    """
    return VStack(
        gap="md",
        key="cat-action",
        children=[
            HStack(
                gap="sm",
                key="btns",
                children=[
                    Button(label="Solid", variant=Variant.SOLID, theme=theme, key="b1"),
                    Button(
                        label="Outline", variant=Variant.OUTLINE, theme=theme, key="b2"
                    ),
                    Button(label="Ghost", variant=Variant.GHOST, theme=theme, key="b3"),
                    Button(label="Link", variant=Variant.LINK, theme=theme, key="b4"),
                ],
            ),
            HStack(
                gap="sm",
                key="icons",
                children=[
                    IconButton(icon="add", label="Add", theme=theme, key="ib1"),
                    IconButton(
                        icon="settings",
                        label="Settings",
                        variant=Variant.SOLID,
                        theme=theme,
                        key="ib2",
                    ),
                ],
            ),
        ],
    )


def _inputs(theme: Theme) -> Widget:
    """Build the Inputs category specimens.

    Args:
        theme: The active design-system theme.

    Returns:
        A column of input-component specimens.
    """
    return VStack(
        gap="md",
        key="cat-inputs",
        children=[
            Input(value="Maria", placeholder="Name", theme=theme, key="in1"),
            HStack(
                gap="md",
                key="sel",
                children=[
                    Checkbox(checked=True, label="Agree", theme=theme, key="cb"),
                    Switch(checked=True, label="On", theme=theme, key="sw"),
                ],
            ),
            Slider(value=0.6, theme=theme, key="sl"),
        ],
    )


def _surfaces(theme: Theme) -> Widget:
    """Build the Surfaces category specimens.

    Args:
        theme: The active design-system theme.

    Returns:
        A row of card-variant specimens.
    """
    return HStack(
        gap="md",
        key="cat-surfaces",
        children=[
            Card(
                variant=CardVariant.ELEVATED,
                theme=theme,
                key="c1",
                children=[Text(content="Elevated")],
            ),
            Card(
                variant=CardVariant.FILLED,
                theme=theme,
                key="c2",
                children=[Text(content="Filled")],
            ),
            Card(
                variant=CardVariant.OUTLINED,
                theme=theme,
                key="c3",
                children=[Text(content="Outlined")],
            ),
            Surface(
                variant=CardVariant.FILLED,
                theme=theme,
                key="s1",
                child=Text(content="Surface"),
            ),
        ],
    )


def _feedback(theme: Theme) -> Widget:
    """Build the Feedback category specimens.

    Args:
        theme: The active design-system theme.

    Returns:
        A column of feedback-component specimens.
    """
    return VStack(
        gap="sm",
        key="cat-feedback",
        children=[
            Alert(
                title="Success",
                body="It worked.",
                color_scheme="success",
                variant=AlertVariant.SUBTLE,
                theme=theme,
                key="al1",
            ),
            Alert(
                title="Warning",
                body="Careful.",
                color_scheme="warning",
                variant=AlertVariant.SUBTLE,
                theme=theme,
                key="al2",
            ),
            HStack(
                gap="sm",
                key="chips",
                children=[
                    Chip(label="Chip", color_scheme="primary", theme=theme, key="ch"),
                    ConfidenceBadge(confidence=0.84, label="banana", theme=theme,
                                    key="cbf"),
                ],
            ),
            ProgressBar(value=0.6, color_scheme="success", key="pb"),
        ],
    )


def _navigation(theme: Theme, tab: int) -> Widget:
    """Build the Navigation category specimens.

    Args:
        theme: The active design-system theme.
        tab: The current tab index (re-used as a fake nav selection).

    Returns:
        A column of navigation-component specimens.
    """
    return VStack(
        gap="md",
        key="cat-nav",
        children=[
            NavBar(
                items=["Home", "Search", "Profile"],
                active=tab % 3,
                on_select=lambda _i: None,
                color_scheme="primary",
                theme=theme,
                key="nb",
            ),
            Divider(theme=theme, key="dv"),
            # The H5 Tabs component itself, showcased with a few short labels so
            # its equal-width strip renders cleanly (the top category switcher uses
            # a scrollable strip instead — see _category_strip).
            Tabs(
                tabs=["Home", "Search", "You"],
                active=tab % 3,
                on_select=lambda _i: None,
                color_scheme="primary",
                theme=theme,
                key="nav-tabs",
            ),
        ],
    )


def _research(theme: Theme) -> Widget:
    """Build the Research category specimens.

    Args:
        theme: The active design-system theme.

    Returns:
        A column of research-component specimens.
    """
    return VStack(
        gap="md",
        key="cat-research",
        children=[
            HStack(
                gap="md",
                key="metrics",
                children=[
                    MetricCard(
                        label="Detections",
                        value="2",
                        delta="+1",
                        delta_up=True,
                        color_scheme="primary",
                        theme=theme,
                        key="mc",
                    ),
                ],
            ),
            BarChart(
                values=[0.84, 0.41, 0.18],
                labels=["banana", "apple", "pear"],
                width=420.0,
                height=140.0,
                theme=theme,
                key="bc",
            ),
            DetectionOverlay(
                image_src="",
                boxes=[
                    DetectionBox(x1=0.2, y1=0.2, x2=0.7, y2=0.7, name="banana",
                                 conf=0.84),
                ],
                width=240.0,
                height=160.0,
                theme=theme,
                key="ov",
            ),
        ],
    )


def view(app: App[StoryState]) -> Widget:
    """Build the storybook tree for the current theme/locale/tab.

    Reads ``app.theme`` (light/dark) and ``app.locale`` (LTR/RTL) as context, and
    routes to the active category. The toggles call ``app.set_theme`` /
    ``app.set_locale``; the tab strip mutates state.

    Args:
        app: The application driving the storybook.

    Returns:
        The root widget for the current state.
    """
    theme = app.theme
    dark = theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    rtl = app.locale.rtl
    tab = app.state.tab

    def _toggle_dark() -> None:
        """Flip the theme mode."""
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    def _toggle_rtl() -> None:
        """Flip the locale direction."""
        app.set_locale(
            Locale(language="pt", region="BR", rtl=False)
            if rtl
            else Locale(language="ar", region="EG", rtl=True)
        )

    bodies = {
        0: _action(theme),
        1: _inputs(theme),
        2: _surfaces(theme),
        3: _feedback(theme),
        4: _navigation(theme, tab),
        5: _research(theme),
    }

    return Column(
        style=Style(gap=12.0, padding=Edge.all(12.0)),
        key="root",
        children=[
            AppBar(
                title="Design system",
                color_scheme="primary",
                theme=theme,
                actions=[
                    Button(
                        label="Dark" if not dark else "Light",
                        variant=Variant.GHOST,
                        size=Size.SM,
                        on_click=_toggle_dark,
                        theme=theme,
                        key="t-dark",
                    ),
                    Button(
                        label="RTL" if not rtl else "LTR",
                        variant=Variant.GHOST,
                        size=Size.SM,
                        on_click=_toggle_rtl,
                        theme=theme,
                        key="t-rtl",
                    ),
                ],
                key="bar",
            ),
            _category_strip(
                theme,
                tab,
                lambda i: app.set_state(lambda _s: StoryState(tab=i)),
            ),
            bodies[tab],
        ],
    )


def _category_strip(
    theme: Theme, active: int, on_select: Callable[[int], None]
) -> Widget:
    """Build a horizontally-scrollable category switcher.

    The top-level switcher has 6 categories — too many for an equal-width
    :class:`~tempestroid.Tabs` strip on a phone (the labels would wrap
    character-by-character). A horizontal :class:`~tempestroid.ScrollView` of
    content-sized GHOST buttons keeps every label on one line and lets the strip
    scroll; the active category takes the ``primary`` accent.

    Args:
        theme: The active design-system theme.
        active: The selected category index.
        on_select: Called with a category index when its button is tapped.

    Returns:
        A scrollable row of category buttons.
    """
    buttons = [
        Button(
            label=label,
            variant=Variant.GHOST,
            size=Size.SM,
            color_scheme="primary" if index == active else "neutral",
            theme=theme,
            on_click=lambda index=index: on_select(index),
            key=f"cat-{index}",
        )
        for index, label in enumerate(_CATEGORIES)
    ]
    return ScrollView(
        horizontal=True,
        children=[Row(children=buttons, style=Style(gap=4.0))],
        key="tabs",
    )


def main() -> None:
    """Run the storybook in the Qt simulator (lazy import keeps the module clean)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(make_state(), view)


if __name__ == "__main__":
    main()
