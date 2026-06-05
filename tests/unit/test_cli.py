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


def test_build_dispatches_to_apk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`tempest build` (no --release) builds a debug APK via Gradle build_apk.

    The applicationId is derived from the project name when --app-id is omitted,
    so two distinct projects produce distinct ids (installable side by side).
    """
    from tempestroid.cli import release_build

    app = tmp_path / "myapp"
    app.mkdir()
    (app / "pyproject.toml").write_text('[tool.tempest]\napp = "main.py"\n')
    (app / "main.py").write_text(
        "def make_state():\n    ...\ndef view(app):\n    ...\n"
    )

    seen: dict[str, object] = {}

    def fake_build_apk(_app: object, *, app_id: str, **_kw: object) -> Path:
        seen["app_id"] = app_id
        return tmp_path / "out.apk"

    monkeypatch.setattr(release_build, "build_apk", fake_build_apk)
    assert main(["build", str(app / "main.py")]) == 0
    assert seen["app_id"] == "com.example.myapp"


def test_build_uses_given_app_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An explicit --app-id is passed straight through to the debug APK build."""
    from tempestroid.cli import release_build

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    captured: dict[str, object] = {}

    def fake_build_apk(_app: object, *, app_id: str, **_kw: object) -> Path:
        captured["app_id"] = app_id
        return tmp_path / "out.apk"

    monkeypatch.setattr(release_build, "build_apk", fake_build_apk)
    assert main(["build", str(app), "--app-id", "com.acme.todo"]) == 0
    assert captured["app_id"] == "com.acme.todo"


def test_build_fast_uses_repackage_not_gradle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`tempest build --fast` repackages the prebuilt host, skipping Gradle.

    The `--fast` path must call `package_app_apk` (SDK build-tools only) and must
    NOT touch the Gradle `build_apk`, so it works from a PyPI install without a
    source checkout / NDK.
    """
    from tempestroid.cli import packaging, release_build

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")

    calls: dict[str, object] = {}

    def fake_package_app_apk(_app: object, **_kw: object) -> Path:
        calls["repackaged"] = True
        return tmp_path / "out.apk"

    def fail_build_apk(*_a: object, **_k: object) -> Path:
        raise AssertionError("--fast must not call the Gradle build_apk")

    monkeypatch.setattr(packaging, "package_app_apk", fake_package_app_apk)
    monkeypatch.setattr(release_build, "build_apk", fail_build_apk)
    assert main(["build", str(app), "--fast"]) == 0
    assert calls.get("repackaged") is True


def test_build_reports_gradle_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    # When a prepare step fails (e.g. no JDK) build_apk raises StepError; the CLI
    # reports it with exit 1 rather than crashing.
    from tempestroid.cli import release_build
    from tempestroid.cli.console import StepError

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    monkeypatch.chdir(tmp_path)

    def _fail(*_a: object, **_k: object) -> object:
        raise StepError("a JDK is required (test)")

    monkeypatch.setattr(release_build, "build_apk", _fail)
    assert main(["build", str(app)]) == 1


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


def test_build_release_dispatches_to_aab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`tempest build --release` builds an AAB via build_aab, deriving an app-id."""
    from tempestroid.cli import release_build

    app = tmp_path / "myapp"
    app.mkdir()
    (app / "pyproject.toml").write_text('[tool.tempest]\napp = "main.py"\n')
    (app / "main.py").write_text(
        "def make_state():\n    ...\ndef view(app):\n    ...\n"
    )

    seen: dict[str, object] = {}

    def fake_build_aab(app_arg: object, config: object, **_kw: object) -> Path:
        seen["app"] = app_arg
        seen["app_id"] = config.app_id  # type: ignore[attr-defined]
        return tmp_path / "out.aab"

    monkeypatch.setattr(release_build, "build_aab", fake_build_aab)
    assert main(["build", str(app / "main.py"), "--release"]) == 0
    # No --app-id → a derived placeholder from the project dir name.
    assert seen["app_id"] == "com.example.myapp"


def test_build_release_uses_given_app_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An explicit --app-id is passed straight through to the release config."""
    from tempestroid.cli import release_build

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    captured: dict[str, object] = {}

    def fake_build_aab(_app: object, config: object, **_kw: object) -> Path:
        captured["app_id"] = config.app_id  # type: ignore[attr-defined]
        captured["version"] = config.version_name  # type: ignore[attr-defined]
        return tmp_path / "out.aab"

    monkeypatch.setattr(release_build, "build_aab", fake_build_aab)
    rc = main(
        ["build", str(app), "--release", "--app-id", "com.acme.todo",
         "--app-version", "2.1.0"]
    )
    assert rc == 0
    assert captured == {"app_id": "com.acme.todo", "version": "2.1.0"}
