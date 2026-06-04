"""Tests for the Android build-environment configurator (``tempest setup``).

These exercise the probe + JDK detection + URL/version logic without touching the
network or installing anything (the actual SDK download/sdkmanager run needs
network + a JDK, validated on the maintainer's host, not in CI).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tempestroid.cli.console import Console
from tempestroid.cli.setup_env import (
    BUILD_TOOLS,
    COMPILE_SDK,
    NDK_VERSION,
    default_sdk_dir,
    jdk_ok,
    probe_build_env,
    setup_build_env,
)


def _which_java(_name: str) -> str:
    """Stub ``shutil.which`` resolving java."""
    return "/usr/bin/java"


def _which_none(_name: str) -> None:
    """Stub ``shutil.which`` resolving nothing."""
    return None


def test_default_sdk_dir_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANDROID_SDK_ROOT", str(tmp_path))
    assert default_sdk_dir() == tmp_path


def test_default_sdk_dir_falls_back_to_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    # Pretend the system SDK fallback is absent so resolution reaches the managed dir.
    monkeypatch.setattr(
        "tempestroid.cli.setup_env._SYSTEM_SDK_FALLBACK", tmp_path / "no-system-sdk"
    )
    result = default_sdk_dir()
    assert result.name == "android-sdk"
    assert result.parent.name == ".tempestroid"


def test_jdk_ok_parses_modern_version(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_java)

    def fake_run(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        err = 'openjdk version "21.0.3" 2024-04-16\nOpenJDK Runtime Environment'
        return subprocess.CompletedProcess([], 0, stdout="", stderr=err)

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, detail = jdk_ok()
    assert ok is True
    assert "21" in detail


def test_jdk_ok_rejects_old_version(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_java)

    def fake_run(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [], 0, stdout="", stderr='java version "1.8.0_392"'
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, detail = jdk_ok()
    assert ok is False
    assert "need JDK" in detail


def test_jdk_ok_missing_java(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_none)
    ok, detail = jdk_ok()
    assert ok is False
    assert "PATH" in detail


def test_probe_flags_empty_sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_none)  # no java
    sdk = tmp_path / "empty-sdk"
    checks = {c.name: c for c in probe_build_env(sdk)}
    # Empty SDK dir → every SDK-side piece is missing with a hint.
    assert checks["jdk"].ok is False
    assert checks["android-sdk"].ok is False
    assert checks["cmdline-tools"].ok is False
    assert checks["ndk"].ok is False
    assert checks["build-tools"].ok is False
    for name in ("android-sdk", "cmdline-tools", "ndk", "build-tools"):
        assert checks[name].hint  # actionable remediation present


def test_probe_detects_installed_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("shutil.which", _which_none)
    sdk = tmp_path / "sdk"
    # Lay out the dirs the probe looks for at the pinned versions.
    (sdk / "cmdline-tools" / "latest" / "bin").mkdir(parents=True)
    name = "sdkmanager.bat" if sys.platform.startswith("win") else "sdkmanager"
    (sdk / "cmdline-tools" / "latest" / "bin" / name).write_text("#!/bin/sh\n")
    (sdk / "ndk" / NDK_VERSION).mkdir(parents=True)
    (sdk / "build-tools" / BUILD_TOOLS).mkdir(parents=True)
    checks = {c.name: c for c in probe_build_env(sdk)}
    assert checks["android-sdk"].ok is True
    assert checks["cmdline-tools"].ok is True
    assert checks["ndk"].ok is True
    assert checks["build-tools"].ok is True


def test_setup_diagnose_reports_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("shutil.which", _which_none)
    import io

    stream = io.StringIO()
    rc = setup_build_env(
        sdk_dir=tmp_path / "nope", install=False, console=Console(stream=stream)
    )
    assert rc == 1
    out = stream.getvalue()
    assert "tempest setup --install" in out


def test_compile_sdk_and_build_tools_pinned():
    # Guard the pinned versions match what android-host expects (compileSdk 35).
    assert COMPILE_SDK == "35"
    assert BUILD_TOOLS.startswith("35.")
