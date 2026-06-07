"""Tests for the curated icon set (``tempestroid.icons``)."""

from __future__ import annotations

import pytest

from tempestroid import ICON_PATHS, Icons, icon_names, icon_path


def test_icons_enum_values_match_path_keys() -> None:
    """Every ``Icons`` member maps to an ``ICON_PATHS`` entry and vice versa."""
    enum_values = {member.value for member in Icons}
    assert enum_values == set(ICON_PATHS)
    assert len(ICON_PATHS) == len(Icons)


def test_icon_names_sorted_and_complete() -> None:
    """``icon_names`` returns every curated name, sorted."""
    names = icon_names()
    assert names == sorted(ICON_PATHS)
    assert "eye" in names
    assert "eye-off" in names
    assert "lock" in names


def test_icon_path_resolves_enum_and_str() -> None:
    """``icon_path`` accepts an ``Icons`` member or a raw string."""
    assert icon_path(Icons.EYE) == ICON_PATHS["eye"]
    assert icon_path("eye") == ICON_PATHS["eye"]
    assert icon_path(Icons.EYE) == icon_path("eye")


def test_icon_path_unknown_returns_none() -> None:
    """An unknown name resolves to ``None`` rather than raising."""
    assert icon_path("definitely-not-an-icon") is None


@pytest.mark.parametrize("name", sorted(ICON_PATHS))
def test_every_path_is_a_nonempty_svg_d_string(name: str) -> None:
    """Each icon's path data is a non-empty string starting with a move command."""
    d = ICON_PATHS[name]
    assert isinstance(d, str)
    assert d.strip()
    assert d.lstrip()[0] in "Mm", f"{name} path should start with a move command"
