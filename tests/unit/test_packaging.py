"""Tests for ``tempest build`` / ``tempest run`` packaging helpers.

These exercise the host-tree discovery and source-staging logic without an
Android SDK/NDK present (the actual Gradle/adb invocations need the toolchain
and a device, validated on the maintainer's host, not in CI).
"""

from pathlib import Path

import pytest

from tempestroid.cli.packaging import (
    ToolchainError,
    find_android_host,
    stage_app_source,
)


def _make_host(root: Path) -> Path:
    """Create a fake android-host tree with a gradlew marker."""
    host = root / "android-host"
    host.mkdir(parents=True)
    (host / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    return host


def test_find_host_via_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    host = _make_host(tmp_path)
    monkeypatch.setenv("TEMPESTROID_ANDROID_HOST", str(host))
    assert find_android_host() == host.resolve()


def test_env_override_without_gradlew_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TEMPESTROID_ANDROID_HOST", str(tmp_path))
    with pytest.raises(ToolchainError):
        find_android_host()


def test_find_host_walks_upward(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TEMPESTROID_ANDROID_HOST", raising=False)
    host = _make_host(tmp_path)
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert find_android_host(nested) == host.resolve()


def test_find_host_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TEMPESTROID_ANDROID_HOST", raising=False)
    with pytest.raises(ToolchainError):
        find_android_host(tmp_path)


def test_stage_app_source_copies(tmp_path: Path):
    host = _make_host(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("# my app\n", encoding="utf-8")
    asset = stage_app_source(app, host)
    assert asset == host / "app" / "src" / "main" / "assets" / "tempest_app.py"
    assert asset.read_text(encoding="utf-8") == "# my app\n"


def test_stage_missing_app_raises(tmp_path: Path):
    host = _make_host(tmp_path)
    with pytest.raises(FileNotFoundError):
        stage_app_source(tmp_path / "nope.py", host)
