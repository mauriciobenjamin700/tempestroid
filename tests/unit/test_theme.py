"""Unit tests for the phase-E9 theme / media-query / i18n context."""

import asyncio
import json
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from tempestroid import (
    App,
    Color,
    Locale,
    LocaleChangeEvent,
    MediaQueryData,
    Text,
    Theme,
    ThemeChangeEvent,
    ThemeMode,
    Widget,
    parse_event,
    t,
    translate,
)
from tempestroid.widgets.events import EventValidationError


@dataclass
class _State:
    value: int = 0


def _view(app: "App[_State]") -> Widget:
    label = "dark" if app.theme.is_dark(
        platform_dark_mode=app.media.platform_dark_mode
    ) else "light"
    return Text(content=f"{label}:{app.locale.language}")


def test_theme_constructs_with_palette() -> None:
    theme = Theme(
        mode=ThemeMode.DARK,
        primary=Color(r=10, g=20, b=30),
        background=Color.from_hex("#000000"),
    )
    assert theme.mode is ThemeMode.DARK
    assert theme.primary == Color(r=10, g=20, b=30)
    assert theme.background == Color(r=0, g=0, b=0)


def test_theme_is_frozen() -> None:
    theme = Theme()
    with pytest.raises(ValidationError):
        theme.mode = ThemeMode.DARK  # type: ignore[misc]


def test_theme_is_dark_resolution() -> None:
    assert Theme(mode=ThemeMode.DARK).is_dark() is True
    assert Theme(mode=ThemeMode.LIGHT).is_dark(platform_dark_mode=True) is False
    assert Theme(mode=ThemeMode.SYSTEM).is_dark(platform_dark_mode=True) is True
    assert Theme(mode=ThemeMode.SYSTEM).is_dark(platform_dark_mode=False) is False


def test_media_query_roundtrip_json() -> None:
    media = MediaQueryData(
        width=412.0,
        height=915.0,
        device_pixel_ratio=2.625,
        text_scale_factor=1.3,
        platform_dark_mode=True,
        orientation="landscape",
    )
    raw = json.dumps(media.model_dump())
    restored = MediaQueryData.model_validate(json.loads(raw))
    assert restored == media


def test_locale_rtl_flag() -> None:
    ar = Locale(language="ar", region="EG", rtl=True)
    assert ar.rtl is True
    assert ar.tag == "ar-EG"
    assert Locale().tag == "pt"


def test_translate_and_alias_interpolate() -> None:
    tables = {
        "pt": {"hello": "Olá, {name}"},
        "en": {"hello": "Hello, {name}"},
    }
    assert translate("hello", Locale(language="pt"), tables, name="Ana") == "Olá, Ana"
    assert t("hello", Locale(language="en"), tables, name="Bob") == "Hello, Bob"
    # Missing key falls back to the key itself.
    assert translate("bye", Locale(language="pt"), tables) == "bye"
    # Missing language falls back to the key.
    assert translate("hello", Locale(language="fr"), tables, name="X") == "hello"


def test_theme_change_event_parses() -> None:
    event = parse_event(ThemeChangeEvent, {"mode": "dark"})
    assert event.mode is ThemeMode.DARK
    with pytest.raises(EventValidationError):
        parse_event(ThemeChangeEvent, {"mode": "neon"})


def test_locale_change_event_parses() -> None:
    event = parse_event(
        LocaleChangeEvent, {"language": "ar", "region": "EG", "rtl": True}
    )
    assert (event.language, event.region, event.rtl) == ("ar", "EG", True)
    # rtl/region optional.
    minimal = parse_event(LocaleChangeEvent, {"language": "en"})
    assert minimal.region is None and minimal.rtl is False


def test_app_defaults_theme_media_locale() -> None:
    app: App[_State] = App(_State(), _view, apply_patches=lambda _p: None)
    assert app.theme == Theme()
    assert app.media == MediaQueryData()
    assert app.locale == Locale()


def test_app_accepts_initial_context() -> None:
    app: App[_State] = App(
        _State(),
        _view,
        apply_patches=lambda _p: None,
        theme=Theme(mode=ThemeMode.DARK),
        media=MediaQueryData(platform_dark_mode=True),
        locale=Locale(language="en"),
    )
    assert app.theme.mode is ThemeMode.DARK
    assert app.media.platform_dark_mode is True
    assert app.locale.language == "en"


async def test_set_theme_triggers_rebuild() -> None:
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    scene = app.start()
    assert scene.root.props["content"] == "light:pt"
    app.set_theme(Theme(mode=ThemeMode.DARK))
    await asyncio.sleep(0)
    assert len(captured) == 1
    assert app.current_tree is not None
    assert app.current_tree.root.props["content"] == "dark:pt"


async def test_set_locale_triggers_rebuild() -> None:
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app.set_locale(Locale(language="ar", rtl=True))
    await asyncio.sleep(0)
    assert len(captured) == 1
    assert app.locale.rtl is True
    assert app.current_tree is not None
    assert app.current_tree.root.props["content"] == "light:ar"


async def test_update_media_triggers_rebuild() -> None:
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app._update_media(MediaQueryData(platform_dark_mode=True))  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    await asyncio.sleep(0)
    # With SYSTEM theme + platform dark mode, the view flips to "dark".
    assert len(captured) == 1
    assert app.current_tree is not None
    assert app.current_tree.root.props["content"] == "dark:pt"


async def test_context_changes_coalesce_in_one_tick() -> None:
    captured: list[list[object]] = []
    app: App[_State] = App(
        _State(), _view, apply_patches=lambda p: captured.append(list(p))
    )
    app.start()
    app.set_theme(Theme(mode=ThemeMode.DARK))
    app.set_locale(Locale(language="en"))
    await asyncio.sleep(0)
    # Two context mutations in one tick → a single coalesced rebuild/apply.
    assert len(captured) == 1
    assert app.current_tree is not None
    assert app.current_tree.root.props["content"] == "dark:en"
