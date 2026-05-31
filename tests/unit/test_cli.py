import pytest

from tempestroid.cli import build_parser, main


def test_help_runs_clean():
    assert main([]) == 0


def test_version_flag_exits_zero():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_build_reports_pending():
    assert main(["build"]) == 1


def test_dev_requires_app_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["dev"])  # missing required `app` argument


def test_spec_prints_json(capsys: pytest.CaptureFixture[str]):
    import json

    assert main(["spec"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "widgets" in data and "events" in data
