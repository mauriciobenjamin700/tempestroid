"""H7 capstone: the storybook composes the whole design system across themes.

A representative integration matrix — the ``examples/storybook`` app (every H1–H6
component category) must ``build`` without error in light, dark, and RTL contexts
across all six category tabs, and the dark theme must resolve different colors
than light (proving the live dark re-skin actually flows through ``theme=``).
Complements the per-phase H1–H6 conformance blocks (which pin the resolved Styles
through both translators); this pins that the system *composes* end-to-end.
"""

from __future__ import annotations

import pytest
from tempest_core.core import Node, build
from tempest_core.core.state import App
from tempest_core.i18n import Locale
from tempest_core.theme import Theme, ThemeMode

from tempestroid.cli.app_loader import load_app_spec

_SPEC = load_app_spec("examples/storybook/app.py")
_LTR = Locale(language="pt", region="BR", rtl=False)
_RTL = Locale(language="ar", region="EG", rtl=True)


def _app(theme: Theme, locale: Locale, tab: int) -> App[object]:
    """Build a storybook App in a given theme/locale, parked on ``tab``."""
    app: App[object] = App(
        view=_SPEC.view,
        state=_SPEC.make_state(),
        apply_patches=lambda _p: None,
        theme=theme,
        locale=locale,
    )
    app.state.tab = tab  # type: ignore[attr-defined]
    return app


@pytest.mark.parametrize("mode", [ThemeMode.LIGHT, ThemeMode.DARK])
@pytest.mark.parametrize("locale", [_LTR, _RTL])
@pytest.mark.parametrize("tab", range(6))
def test_storybook_builds_across_theme_locale_tab(
    mode: ThemeMode, locale: Locale, tab: int
) -> None:
    """Every category tab builds in light/dark × LTR/RTL (the system composes)."""
    node = build(_SPEC.view(_app(Theme(mode=mode), locale, tab)))
    assert isinstance(node, Node)
    assert node.type == "Column"


def _backgrounds(node: Node, out: list[str]) -> None:
    """Collect every resolved background color string in the tree."""
    style = node.props.get("style")
    bg = getattr(style, "background", None)
    if bg is not None:
        out.append(repr(bg))
    for child in node.children:
        _backgrounds(child, out)


def test_dark_resolves_different_colors_than_light() -> None:
    """The dark theme re-skins the system — resolved backgrounds differ from light.

    Proves the dark toggle actually flows through ``theme=`` to the components
    (not a no-op): the Surfaces tab's resolved backgrounds are not identical
    between light and dark.
    """
    light: list[str] = []
    dark: list[str] = []
    _backgrounds(build(_SPEC.view(_app(Theme(mode=ThemeMode.LIGHT), _LTR, 2))), light)
    _backgrounds(build(_SPEC.view(_app(Theme(mode=ThemeMode.DARK), _LTR, 2))), dark)
    assert light and dark
    assert set(light) != set(dark)
