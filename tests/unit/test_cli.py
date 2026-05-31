from pathlib import Path

import pytest

from tempestroid.cli import build_parser, main


def test_help_runs_clean():
    assert main([]) == 0


def test_version_flag_exits_zero():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_build_requires_app_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["build"])  # missing required `app` argument


def test_run_requires_app_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run"])  # missing required `app` argument


def test_new_requires_name():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["new"])  # missing required `name` argument


def test_new_scaffolds_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["new", "demo", "--into", str(tmp_path)]) == 0
    project = tmp_path / "demo"
    assert (project / "app.py").is_file()
    assert (project / "README.md").is_file()
    assert "created" in capsys.readouterr().out


def test_new_rejects_existing_dir(tmp_path: Path):
    (tmp_path / "demo").mkdir()
    assert main(["new", "demo", "--into", str(tmp_path)]) == 1


def test_build_reports_missing_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    # No android-host reachable + no override → graceful failure, exit 1.
    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    monkeypatch.delenv("TEMPESTROID_ANDROID_HOST", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["build", str(app)]) == 1
    out = capsys.readouterr().out
    # Preflight surfaces the missing host tree inline before any Gradle work.
    assert "android-host" in out
    assert "could not find the android-host project" in out


def test_dev_requires_app_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["dev"])  # missing required `app` argument


def test_spec_prints_json(capsys: pytest.CaptureFixture[str]):
    import json

    assert main(["spec"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "widgets" in data and "events" in data
