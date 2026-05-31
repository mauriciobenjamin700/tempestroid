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


def test_build_fails_without_android_host(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
):
    # No android-host reachable → build reports failure (exit 1), does not crash.
    monkeypatch.setenv("TEMPEST_ANDROID_HOST", "/nonexistent/android-host")
    monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]
    assert main(["build", "whatever.py"]) == 1


def test_new_scaffolds_app(tmp_path: object, monkeypatch: pytest.MonkeyPatch):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]
    assert main(["new", "demo_app"]) == 0
    assert (Path(str(tmp_path)) / "demo_app" / "app.py").is_file()


def test_dev_requires_app_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["dev"])  # missing required `app` argument


def test_spec_prints_json(capsys: pytest.CaptureFixture[str]):
    import json

    assert main(["spec"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "widgets" in data and "events" in data
