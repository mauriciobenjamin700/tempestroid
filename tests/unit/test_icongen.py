"""Tests for the `tempest icon` asset generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestroid.cli.icongen import generate_assets


def _source(path: Path, size: tuple[int, int] = (300, 200)) -> Path:
    """Write a non-square source image (so cropping is exercised)."""
    from PIL import Image

    Image.new("RGBA", size, (255, 140, 0, 255)).save(path, format="PNG")
    return path


def test_generate_assets_sizes(tmp_path: Path) -> None:
    """The icon is a square of icon_size; the splash a square of splash_size."""
    from PIL import Image

    src = _source(tmp_path / "logo.png")
    out = tmp_path / "assets"
    assets = generate_assets(
        src, out, icon_size=256, splash_size=512, splash_scale=0.5
    )
    assert assets.icon == out / "icon.png"
    assert assets.splash == out / "splash.png"
    with Image.open(assets.icon) as icon:
        assert icon.size == (256, 256)
    with Image.open(assets.splash) as splash:
        assert splash.size == (512, 512)
        # Transparent canvas → the corner pixel is fully transparent (bg shows).
        corner = splash.convert("RGBA").getpixel((0, 0))
        assert isinstance(corner, tuple)
        assert corner[3] == 0


def test_generate_assets_missing_source(tmp_path: Path) -> None:
    """A missing source raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        generate_assets(tmp_path / "nope.png", tmp_path / "out")


def test_generate_assets_bad_scale(tmp_path: Path) -> None:
    """An out-of-range splash scale raises ValueError."""
    src = _source(tmp_path / "logo.png")
    with pytest.raises(ValueError, match="splash_scale"):
        generate_assets(src, tmp_path / "out", splash_scale=0.0)


def test_icon_cmd_generates_and_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`tempest icon` writes both files and prints a build hint."""
    from tempestroid.cli import main

    src = _source(tmp_path / "logo.png")
    out = tmp_path / "assets"
    assert main(["icon", str(src), "--out", str(out)]) == 0
    assert (out / "icon.png").is_file()
    assert (out / "splash.png").is_file()
    printed = capsys.readouterr().out
    assert "tempest build --icon" in printed


def test_icon_cmd_missing_source_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing source fails gracefully (exit 1)."""
    from tempestroid.cli import main

    assert main(["icon", str(tmp_path / "nope.png")]) == 1
    assert "cannot generate assets" in capsys.readouterr().out
