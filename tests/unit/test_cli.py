from pathlib import Path

import pytest

from tempestroid.cli import main


def test_help_runs_clean(capsys: pytest.CaptureFixture[str]):
    assert main(["--help"]) == 0
    assert "Usage" in capsys.readouterr().out


def test_version_flag_exits_zero(capsys: pytest.CaptureFixture[str]):
    assert main(["--version"]) == 0
    assert "tempest" in capsys.readouterr().out


def test_version_command(capsys: pytest.CaptureFixture[str]):
    assert main(["version"]) == 0
    assert "tempest" in capsys.readouterr().out


def test_dev_without_app_or_config_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # No app path + no [tool.tempest] app in cwd → graceful error, exit 1.
    monkeypatch.chdir(tmp_path)
    assert main(["dev"]) != 0


def test_build_without_app_or_config_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) != 0


def test_run_without_app_or_config_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    assert main(["run"]) != 0


def test_dev_reads_configured_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # `tempest dev` with no arg resolves [tool.tempest] app and passes it through
    # to the dev loop (stubbed here so we don't launch a real Qt window).
    (tmp_path / "pyproject.toml").write_text(
        '[tool.tempest]\napp = "myapp.py"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    seen: dict[str, str] = {}

    def fake_run_dev(app: str, verbose: bool) -> int:
        seen["app"] = app
        return 0

    # `tempestroid.cli.main` the attribute is the re-exported `main` function, so
    # reach the module object via sys.modules to patch its `_run_dev`.
    import sys

    main_module = sys.modules["tempestroid.cli.main"]
    monkeypatch.setattr(main_module, "_run_dev", fake_run_dev)
    assert main(["dev"]) == 0
    assert seen["app"] == str((tmp_path / "myapp.py").resolve())


def test_new_scaffolds_named_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["new", "demo", "--into", str(tmp_path)]) == 0
    project = tmp_path / "demo"
    assert (project / "app.py").is_file()
    assert (project / "pyproject.toml").is_file()
    assert (project / "README.md").is_file()
    assert "created" in capsys.readouterr().out


def test_new_scaffolds_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["new", "."]) == 0
    assert (tmp_path / "app.py").is_file()
    assert (tmp_path / "pyproject.toml").is_file()


def test_new_rejects_existing_dir(tmp_path: Path):
    (tmp_path / "demo").mkdir()
    assert main(["new", "demo", "--into", str(tmp_path)]) == 1


def test_build_reports_unresolvable_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    # `tempest build` repackages the prebuilt host APK (no Gradle/android-host).
    # When the host APK can't be resolved (no bundle, no network), it fails
    # gracefully with exit 1 rather than crashing.
    from tempestroid.cli import packaging

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    monkeypatch.chdir(tmp_path)

    def _no_host(*_a: object, **_k: object) -> object:
        raise packaging.ToolchainError("host APK unavailable (test)")

    monkeypatch.setattr(packaging, "resolve_host_apk", _no_host)
    assert main(["build", str(app)]) == 1
    assert "build failed" in capsys.readouterr().out


def test_deploy_reports_missing_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    # `tempest deploy` is the offline path: no Android toolchain required, but it
    # needs a connected device. With adb present and no device it fails gracefully
    # (exit 1) at the device check — never attempting a real deploy.
    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    monkeypatch.chdir(tmp_path)

    def _which(_name: str) -> str:
        return "/usr/bin/adb"

    def _no_devices() -> list[str]:
        return []

    monkeypatch.setattr("shutil.which", _which)
    monkeypatch.setattr("tempestroid.cli.packaging.connected_devices", _no_devices)
    assert main(["deploy", str(app)]) == 1
    out = capsys.readouterr().out
    assert "no ready device" in out


def test_spec_prints_json(capsys: pytest.CaptureFixture[str]):
    import json

    assert main(["spec"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "widgets" in data and "events" in data
