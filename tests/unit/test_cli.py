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


def _assert_scaffold_loads(root: Path) -> None:
    """Load a scaffolded project via the real loader and mount it once.

    Proves the generated tree is importable (renderer-agnostic — no Qt import at
    module top), honors the ``make_state`` + ``view`` contract, and renders to a
    node tree through a real ``App`` — exactly what the device/dev loader does.
    """
    import sys

    from tempestroid.cli.app_loader import spec_from_project
    from tempestroid.core.state import App

    spec = spec_from_project(root, "app.py")
    try:
        app: App[object] = App(
            spec.make_state(), spec.view, apply_patches=lambda _p: None
        )
        scene = app.start()
        assert scene.root is not None
    finally:
        # Drop the project's top-level modules so a second scaffold in the same
        # test session re-imports its own copies (root is added to sys.path).
        for mod in (
            "app", "state", "screens", "components",
            "screens.home", "screens.detail", "screens.native",
            "components.card",
        ):
            sys.modules.pop(mod, None)


def test_new_multi_template_scaffolds(tmp_path: Path):
    """`tempest new -t multi` writes a loadable multi-file project."""
    assert main(["new", "demo", "--into", str(tmp_path), "-t", "multi"]) == 0
    root = tmp_path / "demo"
    assert (root / "state.py").is_file()
    assert (root / "screens" / "home.py").is_file()
    assert (root / "screens" / "detail.py").is_file()
    assert (root / "components" / "card.py").is_file()
    _assert_scaffold_loads(root)


def test_new_native_template_scaffolds(tmp_path: Path):
    """`tempest new -t native` adds a native-capabilities screen and loads."""
    assert main(["new", "demo", "--into", str(tmp_path), "-t", "native"]) == 0
    root = tmp_path / "demo"
    assert (root / "screens" / "native.py").is_file()
    native_src = (root / "screens" / "native.py").read_text(encoding="utf-8")
    assert "get_position" in native_src and "NativeError" in native_src
    _assert_scaffold_loads(root)


def test_new_rejects_unknown_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """An unknown --template fails gracefully (exit 1) listing the valid names."""
    assert main(["new", "demo", "--into", str(tmp_path), "-t", "bogus"]) == 1
    assert "unknown template" in capsys.readouterr().out


@pytest.mark.parametrize("template", ["default", "multi", "native"])
def test_new_in_place_name_with_quote_stays_valid_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str
):
    """An in-place scaffold whose dir name has a quote/backslash still loads.

    Regression: the project name is interpolated into the generated ``.py``
    files; an in-place scaffold takes the (unvalidated) directory name, so a
    name with a double-quote or backslash must be escaped or the generated code
    is invalid Python. Every template's `app.py` must still compile.
    """
    # Build the name from chars so the test source holds no literal with a
    # quote/backslash (which would trip the quote conventions either way).
    weird = tmp_path / f"we{chr(34)}ird{chr(92)}app"
    weird.mkdir()
    monkeypatch.chdir(weird)
    assert main(["new", ".", "-t", template]) == 0
    # The generated entry compiles (escaping kept the literals valid).
    compile((weird / "app.py").read_text(encoding="utf-8"), "app.py", "exec")


def test_prepare_sdk_env_overwrites_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Gradle SDK prep overwrites a STALE ANDROID_HOME/ANDROID_SDK_ROOT.

    Regression: a user shell with `ANDROID_HOME=~/Android` /
    `ANDROID_SDK_ROOT=~/Android/Sdk` (non-existent) made `tempest build`/`run`
    fail "SDK location not found" — AGP read the stale `ANDROID_HOME`. The prep
    must force BOTH vars to the resolved SDK (not `setdefault`).
    """
    import os

    from tempestroid.cli import release_build
    from tempestroid.cli.console import Console

    sdk = tmp_path / "sdk"
    (sdk / "ndk").mkdir(parents=True)
    (sdk / "platform-tools").mkdir()
    monkeypatch.setattr(release_build, "default_sdk_dir", lambda: sdk)

    def _no_install(*_a: object, **_k: object) -> None:
        raise AssertionError("must not install when the SDK is already complete")

    monkeypatch.setattr(release_build, "install_android_sdk", _no_install)
    monkeypatch.setenv("ANDROID_HOME", "/stale/home")
    monkeypatch.setenv("ANDROID_SDK_ROOT", "/stale/sdk")

    prepare = release_build._prepare_sdk_env  # pyright: ignore[reportPrivateUsage]
    resolved = prepare(Console())
    assert resolved == sdk
    assert os.environ["ANDROID_HOME"] == str(sdk)
    assert os.environ["ANDROID_SDK_ROOT"] == str(sdk)


def test_build_falls_back_to_repackage_when_gradle_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`tempest build` falls back to the repackage when the Gradle toolchain fails.

    The Gradle path needs the full SDK/NDK + CPython-Android toolchain, often
    absent from a PyPI install. When `build_apk` raises (a prep `StepError` or a
    Gradle `CalledProcessError`), the CLI must fall back to the toolchain-free
    `package_app_apk` (repackage) and still produce an APK — not exit 1.
    """
    from pathlib import Path as _P

    from tempestroid.cli import packaging, release_build
    from tempestroid.cli.console import StepError

    app = tmp_path / "app.py"
    app.write_text("def make_state():\n    ...\ndef view(app):\n    ...\n")
    monkeypatch.chdir(tmp_path)

    def _gradle_fails(*_a: object, **_k: object) -> object:
        raise StepError("a JDK is required (test)")

    calls: dict[str, object] = {}

    def fake_repackage(_app: object, **_kw: object) -> _P:
        calls["repackaged"] = True
        return tmp_path / "out.apk"

    monkeypatch.setattr(release_build, "build_apk", _gradle_fails)
    monkeypatch.setattr(packaging, "package_app_apk", fake_repackage)
    assert main(["build", str(app)]) == 0
    assert calls.get("repackaged") is True
    assert "falling back" in capsys.readouterr().out.lower()


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


def test_build_apk_reads_id_from_tool_tempest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`tempest build apk` reads the applicationId from [tool.tempest] (no flag).

    Config-driven: `id`/`name` in pyproject drive a short `tempest build apk`,
    so each project ships its own id (N apps side by side) without a flag soup.
    """
    from tempestroid.cli import release_build

    app = tmp_path / "todo"
    app.mkdir()
    (app / "pyproject.toml").write_text(
        '[tool.tempest]\napp = "app.py"\nid = "com.acme.todo"\nname = "Todo"\n'
    )
    (app / "app.py").write_text(
        "def make_state():\n    ...\ndef view(app):\n    ...\n"
    )
    monkeypatch.chdir(app)

    seen: dict[str, object] = {}

    def fake_build_apk(
        _app: object, *, app_id: str, app_name: str, **_kw: object
    ) -> Path:
        seen["app_id"] = app_id
        seen["app_name"] = app_name
        return tmp_path / "out.apk"

    monkeypatch.setattr(release_build, "build_apk", fake_build_apk)
    assert main(["build", "apk"]) == 0
    assert seen["app_id"] == "com.acme.todo"
    assert seen["app_name"] == "Todo"


def test_build_release_dispatches_to_aab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`tempest build prd` builds an AAB via build_aab, deriving an app-id."""
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
    assert main(["build", "prd", "--app", str(app / "main.py")]) == 0
    # No id (flag or [tool.tempest]) → a derived placeholder from the project dir.
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
        ["build", "prd", "--app", str(app), "--app-id", "com.acme.todo",
         "--app-version", "2.1.0"]
    )
    assert rc == 0
    assert captured == {"app_id": "com.acme.todo", "version": "2.1.0"}


def test_clean_cache_removes_dirs_keeps_keystore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from tempestroid.cli import release_build

    monkeypatch.setattr(release_build, "_CACHE", tmp_path)
    (tmp_path / "host-extracted").mkdir()
    (tmp_path / "host-src").mkdir()
    (tmp_path / "src").mkdir()
    keystore = tmp_path / "release.jks"
    keystore.write_text("key")

    removed = release_build.clean_cache()

    assert {p.name for p in removed} == {"host-extracted", "host-src", "src"}
    assert not (tmp_path / "host-src").exists()
    assert keystore.exists()  # preserved by default


def test_clean_cache_drops_keystore_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from tempestroid.cli import release_build

    monkeypatch.setattr(release_build, "_CACHE", tmp_path)
    (tmp_path / "release.jks").write_text("key")

    removed = release_build.clean_cache(include_keystore=True)

    assert tmp_path / "release.jks" in removed
    assert not (tmp_path / "release.jks").exists()


def test_clean_command_idempotent_on_empty_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from tempestroid.cli import release_build

    monkeypatch.setattr(release_build, "_CACHE", tmp_path)
    assert main(["clean"]) == 0


def test_doctor_passes_without_device(monkeypatch: pytest.MonkeyPatch):
    """A missing device must not fail doctor — only build readiness does."""
    from tempestroid.cli import packaging
    from tempestroid.cli.packaging import PreflightCheck

    def fake_preflight(*, need_device: bool = False, host: object = None):
        return [
            PreflightCheck("jdk", True, "openjdk 21"),
            PreflightCheck("android-host", True, "bundled in the package"),
            PreflightCheck("android-sdk", True, "/usr/lib/android-sdk"),
            PreflightCheck("adb", False, "not on PATH", "install platform-tools."),
            PreflightCheck("device", False, "none connected"),
        ]

    monkeypatch.setattr(packaging, "preflight", fake_preflight)
    assert main(["doctor"]) == 0


def test_doctor_fails_when_build_prereq_missing(monkeypatch: pytest.MonkeyPatch):
    """A missing build-critical prerequisite (JDK) makes doctor exit non-zero."""
    from tempestroid.cli import packaging
    from tempestroid.cli.packaging import PreflightCheck

    def fake_preflight(*, need_device: bool = False, host: object = None):
        return [
            PreflightCheck("jdk", False, "not found", "install a JDK >= 17."),
            PreflightCheck("android-host", True, "bundled in the package"),
            PreflightCheck("android-sdk", True, "/usr/lib/android-sdk"),
        ]

    monkeypatch.setattr(packaging, "preflight", fake_preflight)
    assert main(["doctor"]) != 0
