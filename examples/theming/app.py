"""Theming, i18n/RTL, and accessibility demo (phase E9).

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/theming/app.py

It exercises the phase-E9 cross-cutting surface:

* a light/dark toggle that calls ``app.set_theme`` (``ThemeMode``);
* a locale toggle between Portuguese (LTR) and Arabic (RTL) via
  ``app.set_locale``, with the strings looked up through ``translate`` (``t``);
* a counter label carrying ``Semantics(label=...)`` so a screen reader can
  describe it.

The ``view`` reads ``app.theme`` / ``app.locale`` / ``app.media`` as *context*
(not nodes in the tree) and builds the screen conditionally — the reconciler
still diffs a plain widget tree.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    AlignItems,
    App,
    Button,
    Color,
    Column,
    Edge,
    FlexDirection,
    FontWeight,
    Locale,
    Row,
    Semantics,
    Style,
    Text,
    Theme,
    ThemeMode,
    Widget,
    t,
)

#: Minimal translation table keyed by language tag.
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": {
        "title": "Contador",
        "count": "Contagem: {value}",
        "toggle_theme": "Tema",
        "toggle_locale": "العربية",
        "increment": "Incrementar",
    },
    "ar": {
        "title": "عداد",
        "count": "العدد: {value}",
        "toggle_theme": "نمط",
        "toggle_locale": "Português",
        "increment": "زيادة",
    },
}


@dataclass
class ThemingState:
    """The demo's mutable state.

    Attributes:
        value: The current count shown by the accessible label.
    """

    value: int = 0


def make_state() -> ThemingState:
    """Build a fresh initial state (used on every hot restart).

    Returns:
        A new state at zero.
    """
    return ThemingState()


def view(app: App[ThemingState]) -> Widget:
    """Build the themed, localized UI for the current context.

    Reads ``app.theme`` (dark/light), ``app.locale`` (language + RTL), and
    ``app.state`` to build the tree. Handlers swap the context via
    ``app.set_theme`` / ``app.set_locale`` and mutate state via ``app.set_state``.

    Args:
        app: The running app.

    Returns:
        The root widget of the screen.
    """
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    locale = app.locale
    bg = "#0b0f14" if dark else "#f9fafb"
    fg = "#f9fafb" if dark else "#111827"
    accent = "#22c55e" if dark else "#2563eb"

    def toggle_theme() -> None:
        new_mode = ThemeMode.LIGHT if dark else ThemeMode.DARK
        app.set_theme(Theme(mode=new_mode))

    def toggle_locale() -> None:
        new = (
            Locale(language="ar", region="EG", rtl=True)
            if locale.language == "pt"
            else Locale(language="pt", region="BR", rtl=False)
        )
        app.set_locale(new)

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def _button_style(background: str) -> Style:
        return Style(
            padding=Edge.symmetric(vertical=10.0, horizontal=18.0),
            radius=10.0,
            background=Color.from_hex(background),
            color=Color.from_hex("#ffffff"),
            font_size=16.0,
        )

    return Column(
        style=Style(
            direction=FlexDirection.COLUMN,
            align=AlignItems.CENTER,
            gap=16.0,
            padding=Edge.all(24.0),
            background=Color.from_hex(bg),
        ),
        children=[
            Text(
                content=t("title", locale, _TRANSLATIONS),
                style=Style(color=Color.from_hex(fg), font_size=22.0,
                            font_weight=FontWeight.BOLD),
                semantics=Semantics(label=t("title", locale, _TRANSLATIONS),
                                    role="heading"),
                key="title",
            ),
            Text(
                content=t("count", locale, _TRANSLATIONS, value=str(app.state.value)),
                style=Style(color=Color.from_hex(fg), font_size=24.0,
                            font_weight=FontWeight.BOLD),
                semantics=Semantics(
                    label=t("count", locale, _TRANSLATIONS, value=str(app.state.value))
                ),
                key="count",
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(
                        label=t("increment", locale, _TRANSLATIONS),
                        on_click=increment,
                        key="inc",
                        style=_button_style(accent),
                    ),
                    Button(
                        label=t("toggle_theme", locale, _TRANSLATIONS),
                        on_click=toggle_theme,
                        key="theme",
                        style=_button_style("#6b7280"),
                    ),
                    Button(
                        label=t("toggle_locale", locale, _TRANSLATIONS),
                        on_click=toggle_locale,
                        key="locale",
                        style=_button_style("#6b7280"),
                    ),
                ],
            ),
        ],
    )


def main() -> int:
    """Run the theming demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — theming", size=(420, 240))


if __name__ == "__main__":
    raise SystemExit(main())
