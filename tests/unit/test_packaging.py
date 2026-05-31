"""Tests for ``tempest build`` / ``tempest run`` packaging helpers.

These exercise the host-tree discovery and source-staging logic without an
Android SDK/NDK present (the actual Gradle/adb invocations need the toolchain
and a device, validated on the maintainer's host, not in CI).
"""

import io
import subprocess
from pathlib import Path

import pytest

from tempestroid.cli.console import Console, StepError
from tempestroid.cli.packaging import (
    PreflightCheck,
    ToolchainError,
    connected_devices,
    find_android_host,
    preflight,
    report_preflight,
    stage_app_source,
)


def _which_adb(_name: str) -> str:
    """Stub ``shutil.which`` that always resolves adb."""
    return "/usr/bin/adb"


def _which_none(_name: str) -> None:
    """Stub ``shutil.which`` that resolves nothing."""
    return None


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


def test_preflight_all_ok_without_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    host = _make_host(tmp_path)
    monkeypatch.setenv("TEMPESTROID_ANDROID_HOST", str(host))
    monkeypatch.setenv("ANDROID_SDK_ROOT", str(tmp_path))
    monkeypatch.setattr("shutil.which", _which_adb)
    checks = preflight(host=host)
    names = {c.name for c in checks}
    assert names == {"android-host", "android-sdk", "adb"}
    assert all(c.ok for c in checks)


def test_preflight_flags_missing_adb_and_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    host = _make_host(tmp_path)
    monkeypatch.setenv("ANDROID_SDK_ROOT", str(tmp_path))
    monkeypatch.setattr("shutil.which", _which_none)
    checks = preflight(need_device=True, host=host)
    by_name = {c.name: c for c in checks}
    assert by_name["adb"].ok is False
    assert by_name["adb"].hint
    assert by_name["device"].ok is False


def test_connected_devices_parses_adb_output(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_adb)

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        out = "List of devices attached\nABC123\tdevice\nXYZ\toffline\n"
        return subprocess.CompletedProcess([], 0, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert connected_devices() == ["ABC123"]


def test_connected_devices_empty_without_adb(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", _which_none)
    assert connected_devices() == []


def test_report_preflight_returns_false_on_failure():
    stream = io.StringIO()
    console = Console(stream=stream)
    checks = [
        PreflightCheck("android-host", True, "/some/host"),
        PreflightCheck("adb", False, "not on PATH", "install platform-tools."),
    ]
    assert report_preflight(checks, console) is False
    output = stream.getvalue()
    assert "✗ adb" in output
    assert "install platform-tools." in output


def test_report_preflight_returns_true_when_all_ok():
    stream = io.StringIO()
    console = Console(stream=stream)
    checks = [PreflightCheck("adb", True, "/usr/bin/adb")]
    assert report_preflight(checks, console) is True


def test_console_step_marks_failure_and_reraises():
    stream = io.StringIO()
    console = Console(stream=stream)
    with pytest.raises(StepError):
        with console.step("doing work"):
            raise StepError("boom")
    output = stream.getvalue()
    assert "→ doing work" in output
    assert "✗ doing work — boom" in output


def test_console_step_marks_success():
    stream = io.StringIO()
    console = Console(stream=stream)
    with console.step("ok work"):
        pass
    assert "✓ ok work" in stream.getvalue()


def test_console_run_command_surfaces_failure_tail():
    stream = io.StringIO()
    console = Console(stream=stream)
    cmd = ["python", "-c", "import sys; sys.stderr.write('kaboom\\n'); sys.exit(3)"]
    with pytest.raises(subprocess.CalledProcessError):
        console.run_command(cmd)
    output = stream.getvalue()
    assert "exit 3" in output
    assert "kaboom" in output
    assert "--verbose" in output
