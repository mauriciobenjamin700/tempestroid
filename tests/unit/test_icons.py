"""Tests for the curated icon set (``tempestroid.icons``)."""

from __future__ import annotations

from pathlib import Path

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


def test_svg_to_path_extracts_and_flattens_shapes() -> None:
    """svg_to_path combines path + circle + line into one d string."""
    from tempestroid import svg_to_path

    svg = (
        '<svg viewBox="0 0 24 24">'
        '<path d="M2 12 L12 2"/>'
        '<circle cx="12" cy="12" r="3"/>'
        '<line x1="0" y1="0" x2="4" y2="4"/>'
        "</svg>"
    )
    d = svg_to_path(svg)
    assert "M2 12 L12 2" in d
    assert "a3.0,3.0" in d  # circle -> two arcs
    assert "M0.0,0.0 L4.0,4.0" in d  # line -> move + line


def test_svg_to_path_reads_a_file(tmp_path: Path) -> None:
    """svg_to_path accepts a filesystem path, not just markup."""
    from tempestroid import svg_to_path

    svg_file = tmp_path / "logo.svg"
    svg_file.write_text('<svg viewBox="0 0 24 24"><path d="M1 1 L2 2"/></svg>')
    assert svg_to_path(svg_file) == "M1 1 L2 2"


def test_svg_to_path_rejects_empty_svg() -> None:
    """An SVG with no drawable shapes raises ValueError."""
    import pytest

    from tempestroid import svg_to_path

    with pytest.raises(ValueError):
        svg_to_path('<svg viewBox="0 0 24 24"><title>x</title></svg>')


def test_register_icon_makes_it_resolvable() -> None:
    """A registered custom icon resolves via icon_path and appears in names."""
    from tempestroid import icon_names, icon_path, register_icon

    d = register_icon("brand-mark", path="M1 1 L9 9")
    assert d == "M1 1 L9 9"
    assert icon_path("brand-mark") == "M1 1 L9 9"
    assert "brand-mark" in icon_names()


def test_register_icon_from_svg_source() -> None:
    """register_icon converts an SVG source via svg_to_path."""
    from tempestroid import icon_path, register_icon

    register_icon("svg-mark", '<svg viewBox="0 0 24 24"><path d="M3 3 L6 6"/></svg>')
    assert icon_path("svg-mark") == "M3 3 L6 6"


def test_register_icon_rejects_curated_name_and_bad_args() -> None:
    """Registering over a curated name, or with bad args, raises ValueError."""
    import pytest

    from tempestroid import register_icon

    with pytest.raises(ValueError):
        register_icon("eye", path="M0 0")  # curated name
    with pytest.raises(ValueError):
        register_icon("x-both", "svg", path="d")  # both source and path
    with pytest.raises(ValueError):
        register_icon("x-none")  # neither


def test_input_icon_fields_accept_icons_and_str() -> None:
    """Input leading/trailing icons accept an Icons member or a raw string."""
    from tempestroid import Icons, Input

    field = Input(leading_icon=Icons.SEARCH, trailing_icon="custom-name")
    assert str(field.leading_icon) == "search"
    assert field.trailing_icon == "custom-name"
