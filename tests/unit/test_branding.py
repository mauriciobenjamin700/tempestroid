"""Tests for per-app build branding (icon + splash)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tempestroid.cli.branding import (
    SPLASH_ASSET,
    SPLASH_BG_ASSET,
    Branding,
    apk_asset_replacements,
    load_branding,
    staged_into_host,
)


def _png(path: Path, payload: bytes = b"PNG-DATA") -> Path:
    """Write a stand-in ``.png`` file (content is opaque to the branding code)."""
    path.write_bytes(payload)
    return path


def test_load_branding_empty() -> None:
    """No flags → an empty branding."""
    branding = load_branding(None, None, None)
    assert branding.is_empty()


def test_load_branding_validates(tmp_path: Path) -> None:
    """Paths must exist + be .png; the colour must be #rrggbb."""
    icon = _png(tmp_path / "icon.png")
    splash = _png(tmp_path / "splash.png")
    branding = load_branding(str(icon), str(splash), "#0b0f14")
    assert branding.icon == icon
    assert branding.splash == splash
    assert branding.splash_bg == "#0b0f14"
    assert not branding.is_empty()

    with pytest.raises(ValueError, match="file not found"):
        load_branding(str(tmp_path / "missing.png"), None, None)
    with pytest.raises(ValueError, match="must be a .png"):
        load_branding(str(_png(tmp_path / "icon.jpg")), None, None)
    with pytest.raises(ValueError, match="#rrggbb"):
        load_branding(None, None, "blue")


def test_apk_asset_replacements_splash_only(tmp_path: Path) -> None:
    """The repackage replacements carry the splash image + bg (never the icon)."""
    icon = _png(tmp_path / "icon.png", b"ICON")
    splash = _png(tmp_path / "splash.png", b"SPLASH")
    branding = Branding(icon=icon, splash=splash, splash_bg="#123456")
    repl = apk_asset_replacements(branding)
    assert repl[SPLASH_ASSET] == b"SPLASH"
    assert repl[SPLASH_BG_ASSET] == b"#123456\n"
    # The icon is a compiled resource — never injected via the repackage path.
    assert not any(b"ICON" == v for v in repl.values())


def test_apk_asset_replacements_empty() -> None:
    """No splash override → no replacements."""
    assert apk_asset_replacements(Branding()) == {}


def _fake_host(root: Path) -> Path:
    """Build a minimal host source tree (mipmaps + default splash assets)."""
    res = root / "app" / "src" / "main" / "res"
    for density in ("mdpi", "xxxhdpi"):
        bucket = res / f"mipmap-{density}"
        bucket.mkdir(parents=True)
        (bucket / "ic_launcher.png").write_bytes(b"DEFAULT-ICON")
        (bucket / "ic_launcher_round.png").write_bytes(b"DEFAULT-RND")
    assets = root / "app" / "src" / "main" / "assets" / "tempest"
    assets.mkdir(parents=True)
    (assets / "splash.png").write_bytes(b"DEFAULT-SPLASH")
    (assets / "splash_bg.txt").write_text("#0b0f14\n", encoding="utf-8")
    return root


def test_staged_into_host_overwrites_then_restores(tmp_path: Path) -> None:
    """Branding overlays the host res/assets during the build, then restores them."""
    host = _fake_host(tmp_path / "host")
    res = host / "app" / "src" / "main" / "res"
    assets = host / "app" / "src" / "main" / "assets" / "tempest"
    icon = _png(tmp_path / "my_icon.png", b"MY-ICON")
    splash = _png(tmp_path / "my_splash.png", b"MY-SPLASH")
    branding = Branding(icon=icon, splash=splash, splash_bg="#abcdef")

    with staged_into_host(host, branding):
        # Inside the context the host carries the overrides.
        assert (res / "mipmap-mdpi" / "ic_launcher.png").read_bytes() == b"MY-ICON"
        assert (res / "mipmap-xxxhdpi" / "ic_launcher_round.png").read_bytes() == (
            b"MY-ICON"
        )
        assert (assets / "splash.png").read_bytes() == b"MY-SPLASH"
        assert (assets / "splash_bg.txt").read_text(encoding="utf-8") == "#abcdef\n"

    # After the context every overwritten file is back to the host default.
    assert (res / "mipmap-mdpi" / "ic_launcher.png").read_bytes() == b"DEFAULT-ICON"
    assert (res / "mipmap-xxxhdpi" / "ic_launcher_round.png").read_bytes() == (
        b"DEFAULT-RND"
    )
    assert (assets / "splash.png").read_bytes() == b"DEFAULT-SPLASH"
    assert (assets / "splash_bg.txt").read_text(encoding="utf-8") == "#0b0f14\n"


def test_staged_into_host_empty_is_noop(tmp_path: Path) -> None:
    """An empty branding leaves the host untouched."""
    host = _fake_host(tmp_path / "host")
    splash = host / "app" / "src" / "main" / "assets" / "tempest" / "splash.png"
    with staged_into_host(host, Branding()):
        assert splash.read_bytes() == b"DEFAULT-SPLASH"
    assert splash.read_bytes() == b"DEFAULT-SPLASH"


def test_load_branding_adaptive(tmp_path: Path) -> None:
    """`--adaptive-icon` + `--icon-bg` validate like the other branding inputs."""
    fg = _png(tmp_path / "fg.png")
    branding = load_branding(None, None, None, str(fg), "#0b0f14")
    assert branding.adaptive_icon == fg
    assert branding.icon_bg == "#0b0f14"
    assert not branding.is_empty()

    with pytest.raises(ValueError, match="file not found"):
        load_branding(None, None, None, str(tmp_path / "missing.png"), None)
    with pytest.raises(ValueError, match="#rrggbb"):
        load_branding(None, None, None, str(fg), "teal")


def test_staged_into_host_adaptive_icon_creates_then_cleans(tmp_path: Path) -> None:
    """Adaptive staging writes the v26 resources, then removes them + their dirs."""
    host = _fake_host(tmp_path / "host")
    res = host / "app" / "src" / "main" / "res"
    fg = _png(tmp_path / "fg.png", b"MY-FG")
    branding = Branding(adaptive_icon=fg, icon_bg="#0b0f14")

    fg_drawable = res / "drawable" / "ic_launcher_foreground.png"
    bg_color = res / "values" / "ic_launcher_background.xml"
    xml = res / "mipmap-anydpi-v26" / "ic_launcher.xml"
    xml_round = res / "mipmap-anydpi-v26" / "ic_launcher_round.xml"

    with staged_into_host(host, branding):
        assert fg_drawable.read_bytes() == b"MY-FG"
        assert "#0b0f14" in bg_color.read_text(encoding="utf-8")
        assert "adaptive-icon" in xml.read_text(encoding="utf-8")
        assert "@drawable/ic_launcher_foreground" in xml.read_text(encoding="utf-8")
        assert xml_round.is_file()

    # Every created file AND its created dir is gone — host left as found.
    for path in (fg_drawable, bg_color, xml, xml_round):
        assert not path.exists()
    assert not (res / "drawable").exists()
    assert not (res / "values").exists()
    assert not (res / "mipmap-anydpi-v26").exists()


def test_staged_into_host_adaptive_default_bg(tmp_path: Path) -> None:
    """Omitting `icon_bg` falls back to the default white background."""
    host = _fake_host(tmp_path / "host")
    res = host / "app" / "src" / "main" / "res"
    fg = _png(tmp_path / "fg.png", b"MY-FG")

    with staged_into_host(host, Branding(adaptive_icon=fg)):
        bg = (res / "values" / "ic_launcher_background.xml").read_text(
            encoding="utf-8"
        )
        assert "#FFFFFF" in bg


def test_inject_bundle_replaces_asset_entries(tmp_path: Path) -> None:
    """The repackage rewrites named asset entries while keeping the rest."""
    from tempestroid.cli.apk_repack import inject_bundle

    host_apk = tmp_path / "host.apk"
    with zipfile.ZipFile(host_apk, "w") as zf:
        zf.writestr(SPLASH_ASSET, b"DEFAULT-SPLASH")
        zf.writestr(SPLASH_BG_ASSET, "#0b0f14\n")
        zf.writestr("lib/arm64-v8a/libfoo.so", b"NATIVE")
    out = tmp_path / "out.apk"
    inject_bundle(
        host_apk,
        b"BUNDLE-ZIP",
        out,
        replacements={SPLASH_ASSET: b"NEW-SPLASH", SPLASH_BG_ASSET: b"#abcdef\n"},
    )
    with zipfile.ZipFile(out) as zf:
        assert zf.read(SPLASH_ASSET) == b"NEW-SPLASH"
        assert zf.read(SPLASH_BG_ASSET) == b"#abcdef\n"
        assert zf.read("lib/arm64-v8a/libfoo.so") == b"NATIVE"
        assert zf.read("assets/tempest_app_bundle.zip") == b"BUNDLE-ZIP"
