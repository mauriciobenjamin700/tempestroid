"""``tempest`` command-line entry point (Typer).

Wires every ``tempest`` sub-command behind a single :class:`typer.Typer`
``app``, mirroring the ``tempest-fastapi-sdk`` CLI conventions (global
``--version``/``-V`` flag plus a ``version`` command, ``no_args_is_help``,
rich markup). ``tempest dev`` runs the interactive simulator cockpit (phase
A5). ``tempest serve`` pushes an app to a device over LAN (phase B5). The
phase-C packaging commands — ``new`` (scaffold), ``build`` (APK), ``run``
(install + logcat) — drive the ``android-host`` Gradle project and ``adb``;
``doctor`` probes their prerequisites without building. ``build``/``run``/
``dev`` accept ``-v``/``--verbose`` for raw command streaming (see
:mod:`tempestroid.cli.console`). Qt is imported lazily inside ``dev`` so
``tempest --help`` works without the optional ``qt`` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from tempestroid.cli.branding import Branding
    from tempestroid.testing import TestReport

__all__ = ["app", "main"]

app: typer.Typer = typer.Typer(
    name="tempest",
    help=(
        "Build native Android apps in typed Python.\n\n"
        "Typical flow:\n"
        "  tempest new myapp     scaffold a project\n"
        "  tempest dev           preview in the desktop simulator (hot reload)\n"
        "  tempest serve         live code-push to a connected device\n"
        "  tempest build apk     a shippable per-app APK (config in pyproject)\n\n"
        "Run `tempest doctor` to check the Android prerequisites, or "
        "`tempest <command> --help` for any command."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _print_version(value: bool) -> None:
    """Print the framework version and exit.

    Args:
        value: True when ``--version`` is passed.

    Raises:
        typer.Exit: Always when ``value`` is True.
    """
    if value:
        from tempestroid import __version__

        typer.echo(f"tempest {__version__}")
        raise typer.Exit()


@app.callback()
def _root(  # pyright: ignore[reportUnusedFunction]  # wired by Typer via the decorator
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the framework version and exit.",
            callback=_print_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Root callback wiring global flags such as --version."""


@app.command("dev", rich_help_panel="Create & develop")
def dev_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option(
            "--device",
            "-d",
            help="Size the simulator to a device preset (e.g. pixel-7, "
            "galaxy-s24, redmi-note-12). Defaults to a generic mid-size phone.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print full tracebacks when a save fails to reload.",
        ),
    ] = False,
) -> None:
    """Run the simulator dev loop."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_dev(resolved, verbose, device))


@app.command("serve", rich_help_panel="Create & develop")
def serve_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind address (default: 0.0.0.0)."),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", help="TCP port (default: 8765)."),
    ] = 8765,
    no_launch: Annotated[
        bool,
        typer.Option(
            "--no-launch",
            help="Just serve; do not auto `adb reverse` + launch the host in "
            "dev mode (launch it yourself).",
        ),
    ] = False,
) -> None:
    """Serve an app to a device over LAN (code-push + log relay)."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_serve(resolved, host, port, launch=not no_launch))


@app.command("install", rich_help_panel="Ship & install")
def install_cmd(
    source: Annotated[
        str | None,
        typer.Argument(
            metavar="[SOURCE]",
            help="Local .apk path or http(s) URL. Default: the host APK bundled "
            "in the package (offline). Override via TEMPESTROID_HOST_APK[_URL].",
        ),
    ] = None,
    no_launch: Annotated[
        bool,
        typer.Option("--no-launch", help="Install only; do not launch the host."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Install the prebuilt host APK on a device (no Android SDK/NDK needed)."""
    raise typer.Exit(_run_install(source, launch=not no_launch, verbose=verbose))


@app.command("spec", rich_help_panel="Diagnose & inspect")
def spec_cmd() -> None:
    """Print the typed contract (widgets/events) as JSON."""
    import json

    from tempestroid import introspect

    print(json.dumps(introspect(), indent=2))
    raise typer.Exit(0)


@app.command("new", rich_help_panel="Create & develop")
def new_cmd(
    name: Annotated[
        str,
        typer.Argument(
            help="Leave empty to scaffold in the CURRENT directory (the default) "
            "using its folder name as the app id — you are already inside your "
            "project/venv. Pass a name only if you want it in a new subdirectory.",
        ),
    ] = ".",
    into: Annotated[
        str,
        typer.Option(
            "--into",
            help="Parent directory for a named project (default: current dir).",
        ),
    ] = ".",
    template: Annotated[
        str,
        typer.Option(
            "--template",
            "-t",
            help="Project template — default (single app.py), multi (state + "
            "screens/ + components/ + Navigator), or native (multi plus a "
            "screen calling native capabilities).",
        ),
    ] = "default",
) -> None:
    """Scaffold a tempestroid app in the current directory.

    Run it from inside your already-created project folder (and virtualenv):
    `tempest new` writes the starter files in place and uses the folder name as
    the app id — no extra wrapping directory. Pass a name to create a new
    subdirectory instead.
    """
    raise typer.Exit(_run_new(name, into, template))


@app.command("icon", rich_help_panel="Ship & install")
def icon_cmd(
    source: Annotated[
        str,
        typer.Argument(help="Source image (logo/mark) to generate assets from."),
    ],
    out: Annotated[
        str,
        typer.Option(
            "--out",
            "-o",
            help="Output directory for icon.png + splash.png (default: ./assets).",
        ),
    ] = "assets",
    icon_size: Annotated[
        int,
        typer.Option("--icon-size", help="Launcher-icon square edge in px."),
    ] = 512,
    splash_size: Annotated[
        int,
        typer.Option("--splash-size", help="Splash canvas square edge in px."),
    ] = 1024,
    splash_scale: Annotated[
        float,
        typer.Option(
            "--splash-scale",
            help="Fraction of the splash canvas the mark occupies (0–1).",
        ),
    ] = 0.5,
    adaptive: Annotated[
        bool,
        typer.Option(
            "--adaptive",
            help="Also generate ic_launcher_foreground.png for an adaptive icon "
            "(feed it to `tempest build --adaptive-icon`).",
        ),
    ] = False,
) -> None:
    """Generate the launcher icon + boot splash from one source image.

    Writes ``icon.png`` + ``splash.png`` ready for
    ``tempest build --icon … --splash …``. With ``--adaptive`` it also writes
    ``ic_launcher_foreground.png`` for an Android adaptive icon (the launcher
    applies its mask) — feed it to ``tempest build --adaptive-icon … --icon-bg …``.
    Needs Pillow (``pip install tempestroid[icons]``).
    """
    raise typer.Exit(
        _run_icon(source, out, icon_size, splash_size, splash_scale, adaptive)
    )


@app.command("build", rich_help_panel="Ship & install")
def build_cmd(
    target: Annotated[
        str,
        typer.Argument(
            metavar="[TARGET]",
            help="What to build: apk (default — a debug, per-app APK to share / "
            "sideload), release-apk (a release-signed standalone APK to "
            "distribute outside the Play Store) or prd (a store-ready release "
            "AAB). A path to an app file is also accepted (builds an apk).",
        ),
    ] = "apk",
    app: Annotated[
        str | None,
        typer.Option(
            "--app",
            "-a",
            help="App file to build. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output", "-o", help="Output path (default: dist/<project>.apk|.aab)."
        ),
    ] = None,
    app_id: Annotated[
        str | None,
        typer.Option(
            "--app-id", help="applicationId override (else [tool.tempest] id)."
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app-name", help="Launcher label override (else [tool.tempest] name)."
        ),
    ] = None,
    app_version: Annotated[
        str | None,
        typer.Option(
            "--app-version", help="versionName override (else config / 1.0.0)."
        ),
    ] = None,
    version_code: Annotated[
        int | None,
        typer.Option("--version-code", help="versionCode override (else 1)."),
    ] = None,
    keystore: Annotated[
        str | None,
        typer.Option(
            "--keystore",
            help="Release keystore (prd / release-apk; default: auto-generated).",
        ),
    ] = None,
    icon: Annotated[
        str | None,
        typer.Option(
            "--icon", help="Launcher-icon PNG override (else [tool.tempest] icon)."
        ),
    ] = None,
    splash: Annotated[
        str | None,
        typer.Option(
            "--splash", help="Boot-splash PNG override (else [tool.tempest] splash)."
        ),
    ] = None,
    splash_bg: Annotated[
        str | None,
        typer.Option(
            "--splash-bg",
            help="Splash bg #rrggbb override (else config / #0b0f14).",
        ),
    ] = None,
    adaptive_icon: Annotated[
        str | None,
        typer.Option(
            "--adaptive-icon",
            help="Adaptive-icon foreground PNG (Gradle only; launcher masks it).",
        ),
    ] = None,
    icon_bg: Annotated[
        str | None,
        typer.Option(
            "--icon-bg",
            help="Adaptive-icon background #rrggbb (with --adaptive-icon).",
        ),
    ] = None,
    fast: Annotated[
        bool,
        typer.Option(
            "--fast",
            "-f",
            help="Advanced: skip Gradle, repackage the prebuilt host (no SDK at "
            "all). Keeps the shared id `org.tempestroid.host` (one app per device).",
        ),
    ] = False,
    from_source: Annotated[
        bool,
        typer.Option(
            "--from-source",
            help="Advanced: stage the full CPython toolchain from source instead "
            "of reusing the prebuilt host natives (slow; needs the NDK).",
        ),
    ] = False,
    feature: Annotated[
        list[str] | None,
        typer.Option(
            "--feature",
            help="Bundle a heavy optional capability (camera/qr/push/video/maps); "
            "repeatable. Adds to [tool.tempest] features. Each opt-in needs a "
            "from-source build (SDK/NDK); the lean default ships none of them.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Echo raw commands + full output."),
    ] = False,
) -> None:
    """Build a shippable APK (or a store AAB) with the whole project baked in.

    `tempest build` / `tempest build apk` → a debug-signed **APK** with the
    project's **own applicationId** (so any number of tempestroid apps install
    side by side, never overwriting each other), reusing the prebuilt host
    natives — needs only a JDK + the Android SDK (no NDK, no CPython toolchain).
    Identity + branding come from `[tool.tempest]` in pyproject.toml
    (`id` / `name` / `icon` / `splash` / `splash_bg` / `version`), so the command
    stays short; flags override per build.

    `tempest build release-apk` → a standalone, **release-signed APK** for
    distributing outside the Play Store (a website, an alternative store, a
    direct link) with the publisher's own key (`--keystore`, else an
    auto-generated one). Verify with `apksigner verify`.

    `tempest build prd` → a store-ready, release-signed **AAB** for the Play
    Store (`--keystore`, else an auto-generated one).

    Advanced: `--fast` repackages the prebuilt host with no SDK at all (but a
    shared id — one app per device); `--from-source` stages the full CPython
    toolchain instead of reusing the prebuilt natives.
    """
    from tempestroid.cli.branding import load_branding
    from tempestroid.cli.project import (
        UnknownFeatureError,
        read_config,
        resolve_features,
    )

    # The positional is the build target; a path slipped there is treated as the
    # app file (so `tempest build app.py` still works).
    target_norm = target.lower()
    app_arg = app
    _targets = {"apk", "prd", "aab", "release", "release-apk", "apk-release"}
    if app_arg is None and target_norm not in _targets:
        app_arg, target_norm = target, "apk"
    resolved = _resolve_app_or_exit(app_arg)

    # `[tool.tempest]` provides the defaults; explicit flags override.
    cfg = read_config(resolved)
    eff_id = app_id or cfg.app_id
    eff_name = app_name or cfg.app_name
    eff_version = app_version or cfg.version or "1.0.0"
    eff_code = version_code if version_code is not None else 1
    try:
        branding = load_branding(
            icon or cfg.icon,
            splash or cfg.splash,
            splash_bg or cfg.splash_bg,
            adaptive_icon or cfg.adaptive_icon,
            icon_bg or cfg.icon_bg,
        )
    except ValueError as exc:
        print(f"cannot build: {exc}")
        raise typer.Exit(1) from exc

    # Features: merge [tool.tempest] + repeated --feature flags, validate, and
    # close over transitive requirements (qr → camera). Any opt-in feature pulls
    # in heavy Gradle deps absent from the lean prebuilt host, so the build must
    # run from source.
    try:
        features = resolve_features((*cfg.features, *(feature or [])))
    except UnknownFeatureError as exc:
        print(f"cannot build: {exc}")
        raise typer.Exit(1) from exc
    feature_list = ", ".join(features)
    if features and fast:
        print(
            "cannot build: --fast cannot add native features "
            f"({feature_list}) — it only repackages the lean prebuilt "
            "host. Drop --fast (a feature build is from-source)."
        )
        raise typer.Exit(1)
    if features and not from_source:
        from_source = True
        print(
            f"info: features {feature_list} require a from-source build "
            "(SDK/NDK) — enabling --from-source."
        )

    is_release = target_norm in {"prd", "aab", "release"}
    is_release_apk = target_norm in {"release-apk", "apk-release"}
    if fast and (is_release or is_release_apk):
        # `--fast` repackages the debug-signed prebuilt host; it can neither
        # produce an AAB nor apply release signing. Refuse rather than silently
        # ignore the flag and hand back a debug artifact the user didn't ask for.
        print(
            f"cannot build: --fast is not supported for the `{target_norm}` "
            "target (it only produces a debug-signed APK). Drop --fast for a "
            "release build."
        )
        raise typer.Exit(1)
    if fast and (branding.icon is not None or branding.adaptive_icon is not None):
        print(
            "warning: --icon/--adaptive-icon are ignored with --fast (the launcher "
            "icon is a compiled resource); the APK keeps the default icon."
        )
    if is_release:
        raise typer.Exit(
            _run_release(
                resolved,
                eff_id,
                eff_name,
                eff_version,
                eff_code,
                keystore,
                output,
                verbose,
                branding,
                from_source,
                features,
            )
        )
    if is_release_apk:
        raise typer.Exit(
            _run_release_apk(
                resolved,
                eff_id,
                eff_name,
                eff_version,
                eff_code,
                keystore,
                output,
                verbose,
                branding,
                from_source,
                features,
            )
        )
    if fast:
        raise typer.Exit(_run_build_fast(resolved, output, verbose, branding))
    raise typer.Exit(
        _run_build(
            resolved,
            eff_id,
            eff_name,
            eff_version,
            eff_code,
            output,
            verbose,
            branding,
            from_source,
            features,
        )
    )


@app.command("deploy", rich_help_panel="Ship & install")
def deploy_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    force_install: Annotated[
        bool,
        typer.Option(
            "--force-install",
            help="Re-install the host APK even if it is already on the device.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Deploy an app to a connected device — offline, no Android SDK/NDK.

    Installs the prebuilt host (bundled in the wheel) if needed, pushes the whole
    project once, launches it, and exits. Great for testing on your own device.
    Use `tempest serve` for live hot reload, or `tempest build` to produce a
    shippable APK (needs the toolchain).
    """
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(_run_deploy(resolved, force_install, verbose))


@app.command("run", rich_help_panel="Ship & install")
def run_cmd(
    app_path: Annotated[
        str | None,
        typer.Argument(
            metavar="[APP]",
            help="Path to the app file. Omitted → read [tool.tempest] app.",
        ),
    ] = None,
    app_id: Annotated[
        str | None,
        typer.Option(
            "--app-id",
            help="applicationId (derived from the project name when omitted).",
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app-name",
            help="Launcher label (derived from the project name when omitted).",
        ),
    ] = None,
    app_version: Annotated[
        str,
        typer.Option("--app-version", help="versionName (default 1.0.0)."),
    ] = "1.0.0",
    version_code: Annotated[
        int,
        typer.Option("--version-code", help="versionCode (default 1)."),
    ] = 1,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Echo raw commands and stream the full adb output.",
        ),
    ] = False,
) -> None:
    """Build a shippable APK, install it on a device, and stream logs."""
    resolved = _resolve_app_or_exit(app_path)
    raise typer.Exit(
        _run_run(resolved, app_id, app_name, app_version, version_code, verbose)
    )


@app.command("doctor", rich_help_panel="Diagnose & inspect")
def doctor_cmd(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show resolution hints."),
    ] = False,
) -> None:
    """Check the Android build/run prerequisites and exit."""
    raise typer.Exit(_run_doctor(verbose))


@app.command("setup", rich_help_panel="Diagnose & inspect")
def setup_cmd(
    install: Annotated[
        bool,
        typer.Option(
            "--install",
            help="Auto-install the Android SDK + NDK into --sdk-dir (needs a JDK).",
        ),
    ] = False,
    sdk_dir: Annotated[
        str | None,
        typer.Option(
            "--sdk-dir",
            help="SDK directory to inspect/install into "
            "(default: $ANDROID_SDK_ROOT or ~/.tempestroid/android-sdk).",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Echo raw commands + full output."),
    ] = False,
) -> None:
    """Configure the Android build environment for `tempest build`.

    Without `--install` it diagnoses what's missing (JDK, SDK, NDK, build-tools,
    staged toolchain) and prints a remediation plan. With `--install` it installs
    the Android SDK + NDK into a managed directory (the JDK and `make toolchain`
    stay guided). Not needed for the offline `tempest deploy` / `serve` paths.
    """
    raise typer.Exit(_run_setup(install, sdk_dir, verbose))


_QUALITY = "Quality (ruff / pyright / pytest)"


@app.command("lint", rich_help_panel=_QUALITY)
def lint_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Path to lint. Defaults to the current directory."),
    ] = ".",
) -> None:
    """Run `ruff check` on the target (lint only, no changes)."""
    from tempestroid.cli.lint import run_ruff_check

    raise typer.Exit(run_ruff_check(target))


@app.command("fix", rich_help_panel=_QUALITY)
def fix_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Path to fix. Defaults to the current directory."),
    ] = ".",
    unsafe: Annotated[
        bool,
        typer.Option(
            "--unsafe",
            help="Also apply ruff's unsafe autofixes (possible behavior "
            "changes); review the diff after.",
        ),
    ] = False,
) -> None:
    """Apply every ruff autofix + format the target in one pass.

    Equivalent to `ruff check --fix` then `ruff format`: sorts/dedupes imports,
    drops unused imports, normalizes quotes/whitespace, indentation, line length
    and blank lines.
    """
    from tempestroid.cli.lint import run_ruff_fix

    raise typer.Exit(run_ruff_fix(target, unsafe=unsafe))


@app.command("format", rich_help_panel=_QUALITY)
def format_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Path to format. Defaults to the current directory."),
    ] = ".",
) -> None:
    """Run `ruff format` on the target (writes files)."""
    from tempestroid.cli.lint import run_ruff_format

    raise typer.Exit(run_ruff_format(target, check=False))


@app.command("fmt-check", rich_help_panel=_QUALITY)
def fmt_check_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Path to inspect. Defaults to the current directory."),
    ] = ".",
) -> None:
    """Run `ruff format --check` on the target (read-only)."""
    from tempestroid.cli.lint import run_ruff_format

    raise typer.Exit(run_ruff_format(target, check=True))


@app.command("type", rich_help_panel=_QUALITY)
def type_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Package/path to type-check."),
    ] = ".",
) -> None:
    """Run `pyright` against the target (strict type check)."""
    from tempestroid.cli.lint import run_pyright

    raise typer.Exit(run_pyright(target))


@app.command("test", rich_help_panel=_QUALITY)
def test_cmd(
    target: Annotated[
        str | None,
        typer.Argument(help="Optional pytest path filter."),
    ] = None,
) -> None:
    """Run `pytest` (forwarding the optional path argument)."""
    from tempestroid.cli.lint import run_pytest

    raise typer.Exit(run_pytest(target))


@app.command("uitest", rich_help_panel=_QUALITY)
def uitest_cmd(
    path: Annotated[
        str,
        typer.Argument(
            metavar="[PATH]",
            help="UI test file: an app module (view + make_state) plus "
            "`async def test_*(page)` functions.",
        ),
    ],
    target: Annotated[
        str,
        typer.Option(
            "--target",
            "-t",
            help="Backend target: `headless` (renderer-agnostic, in-process) or "
            "`emulator` (REAL Compose render on an Android emulator). `qt`/"
            "`device` are reserved.",
        ),
    ] = "headless",
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            "-j",
            help="Emulator instances to run in parallel (`--target emulator` "
            "only). Capped by the host's CPU/RAM.",
        ),
    ] = 1,
) -> None:
    """Run a Playwright-style native UI test file (F9 driver).

    Drives the IR/state/event core with auto-wait (no fixed sleeps): locate nodes
    by key/text/semantics, act with tap/fill, assert with expect_*. The
    `headless` target runs in-process with no renderer; `--target emulator` runs
    the SAME script against a real app on the Compose renderer on an Android
    emulator, sharding across `-j N` isolated instances and saving a real
    screenshot per test.
    """
    raise typer.Exit(_run_uitest(path, target, jobs))


@app.command("check", rich_help_panel=_QUALITY)
def check_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Path to inspect. Defaults to the current directory."),
    ] = ".",
) -> None:
    """Run the full quality gate: lint + fmt-check + type + test."""
    from tempestroid.cli.lint import run_full_check

    raise typer.Exit(run_full_check(target))


@app.command("version", rich_help_panel="Diagnose & inspect")
def version_cmd() -> None:
    """Show the framework version (same as --version)."""
    from tempestroid import __version__

    typer.echo(f"tempest {__version__}")


@app.command("clean", rich_help_panel="Diagnose & inspect")
def clean_cmd(
    include_keystore: Annotated[
        bool,
        typer.Option(
            "--keystore",
            help="Also delete the cached release keystore (blocks future updates).",
        ),
    ] = False,
) -> None:
    """Reset tempestroid's build caches under `~/.tempestroid`.

    Removes the extracted host natives, the bundled-host working copy, and the
    cloned source — all re-created on the next build. Fixes stale-cache build
    failures after a `pip install --upgrade`. The release keystore is kept
    unless `--keystore` is passed.
    """
    raise typer.Exit(_run_clean(include_keystore))


def _resolve_app_or_exit(app_path: str | None) -> str:
    """Resolve the app path from the argument or project config, or exit.

    Args:
        app_path: An explicit path, or ``None`` to read ``[tool.tempest] app``.

    Returns:
        The resolved app file path.

    Raises:
        typer.Exit: With code ``1`` when no app can be resolved.
    """
    from tempestroid.cli.project import AppResolutionError, resolve_app

    try:
        return resolve_app(app_path)
    except AppResolutionError as exc:
        print(exc)
        raise typer.Exit(1) from exc


def _run_dev(app: str, verbose: bool, device: str | None = None) -> int:
    """Dispatch to the Qt dev cockpit, importing Qt lazily.

    Args:
        app: Path to the app file.
        verbose: Print full tracebacks when a save fails to reload.
        device: Optional device-preset name sizing the simulator viewport.

    Returns:
        The process exit code.
    """
    resolved_device = None
    if device is not None:
        from tempest_core.devices import resolve_device

        resolved_device = resolve_device(device)
        if resolved_device is None:
            print(
                f"unknown device {device!r}. Try one like: pixel-7, galaxy-s24, "
                "redmi-note-12 (see the docs for the full list)."
            )
            return 1
    try:
        from tempestroid.renderers.qt import run_dev
    except ImportError:
        print(
            "`tempest dev` needs the `qt` extra. Install it with: "
            'uv sync --extra qt  (or  pip install "tempestroid[qt]").'
        )
        return 1
    return run_dev(app, verbose=verbose, device=resolved_device)


def _lan_ip() -> str:
    """Best-effort LAN IP for the device to reach this machine.

    Returns:
        The local IP, or ``127.0.0.1`` if it cannot be determined.
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _run_serve(app: str, host: str, port: int, *, launch: bool = True) -> int:
    """Serve an app to a device and relay its logs until interrupted.

    When a device is connected and ``launch`` is set, this closes the loop
    automatically: it wires ``adb reverse`` and launches the prebuilt host in
    dev mode pointed at this server, so ``tempest install`` + ``tempest serve``
    is all that's needed to run on hardware (no SDK/NDK or source build).

    Args:
        app: Path to the app file.
        host: Bind address.
        port: TCP port.
        launch: Auto ``adb reverse`` + launch the host in dev mode when a device
            is present. Set ``False`` to only serve.

    Returns:
        The process exit code.
    """
    import subprocess
    import threading
    from pathlib import Path

    from tempestroid.cli.packaging import (
        ToolchainError,
        adb_reverse,
        connected_devices,
        launch_host_dev,
    )
    from tempestroid.devserver import DevServer, render_qr

    server = DevServer(app, host=host, port=port)
    try:
        server.start()
    except OSError as exc:
        print(f"could not start dev server on {host}:{port}: {exc}")
        return 1

    lan_url = f"http://{_lan_ip()}:{server.port}"
    devices = connected_devices()
    device_line = ", ".join(devices) if devices else "none (connect one for USB push)"
    print(render_qr(lan_url))
    print(
        f"tempest dev server on port {server.port}.\n"
        f"  App:     {Path(app).resolve()}\n"
        f"  Devices: {device_line}\n"
        f"  LAN:     {lan_url}\n"
        f"  USB:     adb reverse tcp:{server.port} tcp:{server.port} "
        f"→ http://localhost:{server.port}\n"
        "Edit + save the app file to hot-restart on device. Ctrl-C to stop."
    )
    if launch and devices:
        try:
            adb_reverse(server.port)
            launch_host_dev(server.port)
            print(
                f"launched the host in dev mode on {devices[0]} "
                f"(adb reverse :{server.port} + tempest_dev_url)."
            )
        except (ToolchainError, subprocess.CalledProcessError) as exc:
            print(
                f"could not auto-launch the host ({exc}); launch it manually:\n"
                f"  adb reverse tcp:{server.port} tcp:{server.port}\n"
                f"  adb shell am start -n org.tempestroid.host/.MainActivity "
                f"--es tempest_dev_url http://localhost:{server.port}"
            )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopping dev server.")
    finally:
        server.stop()
    return 0


def _run_install(source: str | None, *, launch: bool, verbose: bool) -> int:
    """Install the prebuilt host APK on a device, reporting the outcome.

    Args:
        source: A local ``.apk`` path or ``http(s)`` URL; ``None`` uses the host
            APK bundled in the package (offline), falling back to a download.
        launch: Launch the host activity after installing.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid import __version__
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, install_host

    console = Console(verbose=verbose)
    try:
        return install_host(source, version=__version__, launch=launch, console=console)
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
        console.fail(f"install failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"adb command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_new(name: str, into: str, template: str) -> int:
    """Scaffold a fully configured app project, reporting the outcome.

    Args:
        name: The project name, or ``"."`` to scaffold in the current directory.
        into: Parent directory to create a named project under.
        template: The project template (``"default"``, ``"multi"``, ``"native"``).

    Returns:
        The process exit code.
    """
    from tempestroid.cli.scaffold import scaffold

    try:
        result = scaffold(name, parent=into, template=template)
    except (ValueError, FileExistsError) as exc:
        print(f"cannot scaffold: {exc}")
        return 1
    where = "." if result.in_place else result.root.name
    cd_hint = "" if result.in_place else f"  cd {where}\n"
    print(
        f"created {result.name} in {result.root}\n"
        f"{cd_hint}"
        "  uv sync                  # install tempestroid + the Qt simulator\n"
        "  uv run tempest dev       # simulator + hot reload (reads pyproject)\n"
        "  uv run tempest install   # adb-install the bundled host (offline)\n"
        "  uv run tempest serve     # push to the device + auto-launch"
    )
    return 0


def _run_icon(
    source: str,
    out: str,
    icon_size: int,
    splash_size: int,
    splash_scale: float,
    adaptive: bool = False,
) -> int:
    """Generate icon.png + splash.png from a source image, reporting the outcome.

    Args:
        source: Path to the source image.
        out: Output directory.
        icon_size: Launcher-icon square edge in px.
        splash_size: Splash canvas square edge in px.
        splash_scale: Fraction of the splash canvas the mark occupies.
        adaptive: Also generate ``ic_launcher_foreground.png`` for an adaptive icon.

    Returns:
        The process exit code.
    """
    from tempestroid.cli.icongen import generate_assets

    try:
        assets = generate_assets(
            source,
            out,
            icon_size=icon_size,
            splash_size=splash_size,
            splash_scale=splash_scale,
            adaptive=adaptive,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"cannot generate assets: {exc}")
        return 1
    lines = [f"wrote {assets.icon}", f"wrote {assets.splash}"]
    if assets.foreground is not None:
        lines.append(f"wrote {assets.foreground}")
    lines.append("Use them with:")
    build = (
        f"  tempest build --icon {assets.icon} --splash {assets.splash} "
        '--splash-bg "#0b0f14"'
    )
    if assets.foreground is not None:
        build += f' \\\n    --adaptive-icon {assets.foreground} --icon-bg "#0b0f14"'
    lines.append(build)
    print("\n".join(lines))
    return 0


def _run_build_fast(
    app: str, output: str | None, verbose: bool, branding: Branding
) -> int:
    """Build a shippable APK by repackaging the prebuilt host (no Gradle).

    The `--fast` path: bundle the whole project and inject it into the prebuilt
    host APK, re-aligned + re-signed via the SDK build-tools only — no Gradle,
    NDK, source checkout, or CPython toolchain. The APK keeps the shared
    ``org.tempestroid.host`` id (an APK repackage cannot rewrite the binary
    manifest's package), so it is for iterating on a single app, not for shipping
    several side by side (use the default Gradle build with ``--app-id`` for
    that). See :func:`tempestroid.cli.packaging.package_app_apk`.

    Args:
        app: Path to the app's entry file to bundle.
        output: Output APK path, or ``None`` for ``dist/<project>.apk``.
        verbose: Echo raw commands and stream full subprocess output.
        branding: Per-app branding (the splash is applied; the icon is ignored on
            this path — see the build command).

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid import __version__
    from tempestroid.cli.apk_repack import ApkToolError
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, package_app_apk

    console = Console(verbose=verbose)
    try:
        package_app_apk(
            app,
            version=__version__,
            console=console,
            output=Path(output) if output else None,
            branding=branding,
        )
    except StepError:
        return 1
    except (ApkToolError, ToolchainError, FileNotFoundError) as exc:
        console.fail(f"build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"apk packaging failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_build(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    output: str | None,
    verbose: bool,
    branding: Branding,
    from_source: bool = False,
    features: tuple[str, ...] = (),
) -> int:
    """Build a shippable, debug-signed per-app APK via Gradle, reporting outcome.

    Runs ``assembleDebug`` stamping a unique ``applicationId`` (derived from the
    project name when ``app_id`` is ``None``) so any number of tempestroid APKs
    install side by side. Reuses the prebuilt host natives by default (JDK + SDK
    only); ``from_source`` stages the full CPython toolchain instead. See
    :func:`tempestroid.cli.release_build.build_apk`.

    Args:
        app: Path to the app's entry file to bundle.
        app_id: The applicationId, or ``None`` to derive one from the project.
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The versionName.
        version_code: The versionCode.
        output: Output APK path, or ``None`` for ``dist/<project>.apk``.
        verbose: Echo raw commands and stream full subprocess output.
        branding: Per-app branding (icon + splash) applied to the build.
        from_source: Stage the CPython toolchain from source instead of reusing
            the prebuilt host natives.
        features: Opted-in build features (camera/qr/push/video/maps) to bundle;
            empty (default) builds lean.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.release_build import build_apk, derive_app_id, derive_app_name

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id or derive_app_id(project_name)
    resolved_name = app_name or derive_app_name(project_name)
    try:
        build_apk(
            app,
            app_id=resolved_id,
            app_name=resolved_name,
            version_name=app_version,
            version_code=version_code,
            console=console,
            output=Path(output) if output else None,
            branding=branding,
            prebuilt=not from_source,
            features=features,
        )
    except FileNotFoundError as exc:
        # A genuinely missing app file — not a toolchain gap. Don't fall back.
        console.fail(f"build failed: {exc}")
        return 1
    except (StepError, subprocess.CalledProcessError) as exc:
        if features:
            # The fast repackage can't add native deps, so falling back would
            # silently drop the requested features. Fail with the real cause.
            reason = (
                f"exit {exc.returncode}"
                if isinstance(exc, subprocess.CalledProcessError)
                else str(exc)
            )
            feature_list = ", ".join(features)
            console.fail(
                f"feature build failed ({reason}). Features "
                f"({feature_list}) need a working from-source toolchain "
                "(SDK/NDK + CPython prefix); `--fast` cannot add them."
            )
            return (
                exc.returncode if isinstance(exc, subprocess.CalledProcessError) else 1
            )
        # The Gradle path needs the full toolchain (SDK/NDK + the CPython-Android
        # prefix + a source checkout) — heavy, and often unavailable from a plain
        # PyPI install. Rather than fail, fall back to the toolchain-free repackage
        # (the `--fast` path): the user still gets a shippable APK. The trade-off
        # is the shared `org.tempestroid.host` id (a repackage can't stamp a
        # per-app id), so side-by-side install needs the toolchain.
        reason = (
            f"exit {exc.returncode}"
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        console.info(
            f"Gradle build unavailable ({reason}) — falling back to the "
            "toolchain-free repackage (`--fast`). The APK keeps the shared id "
            f"`org.tempestroid.host` (not `{resolved_id}`); for a per-app id "
            "prepare the toolchain (`tempest setup --install` + a source checkout)."
        )
        return _run_build_fast(app, output, verbose, branding)
    return 0


def _run_release(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    keystore: str | None,
    output: str | None,
    verbose: bool,
    branding: Branding,
    from_source: bool = False,
    features: tuple[str, ...] = (),
) -> int:
    """Build a store-ready release AAB, preparing the environment, reporting outcome.

    Args:
        app: Path to the app's entry file.
        app_id: The store applicationId, or ``None`` to derive one (with a warning).
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The release versionName.
        version_code: The release versionCode.
        keystore: Path to a release keystore, or ``None`` to auto-generate.
        output: Output ``.aab`` path, or ``None`` for the default.
        verbose: Echo raw commands and stream full subprocess output.
        branding: Per-app branding (icon + splash) applied to the build.
        from_source: Stage the CPython toolchain from source instead of reusing
            the prebuilt host natives.
        features: Opted-in build features (camera/qr/push/video/maps) to bundle;
            empty (default) builds lean.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.release_build import (
        ReleaseConfig,
        build_aab,
        derive_app_id,
        derive_app_name,
    )

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id
    if resolved_id is None:
        # Derive a placeholder id from the project name; a real store upload
        # needs the publisher's own id, so warn loudly.
        resolved_id = derive_app_id(project_name)
        console.info(
            f"no --app-id given; using placeholder {resolved_id!r}. Set --app-id "
            "to your own (e.g. com.yourcompany.app) before publishing."
        )
    config = ReleaseConfig(
        app_id=resolved_id,
        app_name=app_name or derive_app_name(project_name),
        version_name=app_version,
        version_code=version_code,
        keystore=Path(keystore) if keystore else None,
    )
    try:
        build_aab(
            app,
            config,
            console=console,
            output=Path(output) if output else None,
            branding=branding,
            prebuilt=not from_source,
            features=features,
        )
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"release build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"gradle bundleRelease failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_release_apk(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    keystore: str | None,
    output: str | None,
    verbose: bool,
    branding: Branding,
    from_source: bool = False,
    features: tuple[str, ...] = (),
) -> int:
    """Build a standalone release-signed APK, preparing the env, reporting outcome.

    The professional-distribution path: ``gradlew assembleRelease`` with the
    publisher's keystore, producing an APK installable outside the Play Store.
    Unlike the debug ``tempest build`` it does **not** fall back to the
    toolchain-free repackage on a Gradle failure — a release-signed APK requires
    the real build, so a missing toolchain is a hard error the user must resolve.
    See :func:`tempestroid.cli.release_build.build_release_apk`.

    Args:
        app: Path to the app's entry file.
        app_id: The applicationId, or ``None`` to derive one (with a warning).
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The release versionName.
        version_code: The release versionCode.
        keystore: Path to a release keystore, or ``None`` to auto-generate.
        output: Output ``.apk`` path, or ``None`` for the default.
        verbose: Echo raw commands and stream full subprocess output.
        branding: Per-app branding (icon + splash) applied to the build.
        from_source: Stage the CPython toolchain from source instead of reusing
            the prebuilt host natives.
        features: Opted-in build features (camera/qr/push/video/maps) to bundle;
            empty (default) builds lean.

    Returns:
        The process exit code.
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.release_build import (
        ReleaseConfig,
        build_release_apk,
        derive_app_id,
        derive_app_name,
    )

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id
    if resolved_id is None:
        resolved_id = derive_app_id(project_name)
        console.info(
            f"no --app-id given; using placeholder {resolved_id!r}. Set --app-id "
            "to your own (e.g. com.yourcompany.app) before distributing."
        )
    config = ReleaseConfig(
        app_id=resolved_id,
        app_name=app_name or derive_app_name(project_name),
        version_name=app_version,
        version_code=version_code,
        keystore=Path(keystore) if keystore else None,
    )
    try:
        build_release_apk(
            app,
            config,
            console=console,
            output=Path(output) if output else None,
            branding=branding,
            prebuilt=not from_source,
            features=features,
        )
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"release APK build failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"gradle assembleRelease failed (exit {exc.returncode}).")
        return exc.returncode or 1
    return 0


def _run_deploy(app: str, force_install: bool, verbose: bool) -> int:
    """Deploy the app to a connected device offline, reporting the outcome.

    The offline ``tempest deploy`` path: ensure the bundled host is installed,
    push the whole project once, launch, and exit — no Android SDK/NDK, Gradle,
    or ``android-host`` source tree. See :func:`deploy_offline`.

    Args:
        app: Path to the app file to deploy.
        force_install: Re-install the host APK even when already present.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import subprocess

    from tempestroid import __version__
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError, deploy_offline

    console = Console(verbose=verbose)
    try:
        return deploy_offline(
            app,
            version=__version__,
            console=console,
            force_install=force_install,
        )
    except StepError:
        return 1
    except (ToolchainError, FileNotFoundError) as exc:
        console.fail(f"deploy failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_run(
    app: str,
    app_id: str | None,
    app_name: str | None,
    app_version: str,
    version_code: int,
    verbose: bool,
) -> int:
    """Build a shippable APK via Gradle, install + launch it, stream logs.

    The same Gradle build as ``tempest build`` (stamped with a unique
    ``applicationId``), then ``adb install`` + launch + ``logcat``. The launch
    component is ``<app_id>/org.tempestroid.host.MainActivity`` — the activity
    class lives in the fixed ``namespace`` while the package is the per-app id.

    Args:
        app: Path to the app file to bundle.
        app_id: The applicationId, or ``None`` to derive one from the project.
        app_name: The launcher label, or ``None`` to derive it from the project.
        app_version: The versionName.
        version_code: The versionCode.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code.
    """
    import shutil
    import subprocess

    from tempestroid import __version__
    from tempestroid.cli.bundle import resolve_project
    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import connected_devices, package_app_apk
    from tempestroid.cli.release_build import build_apk, derive_app_id, derive_app_name

    console = Console(verbose=verbose)
    project_name = resolve_project(app).root.name
    resolved_id = app_id or derive_app_id(project_name)
    resolved_name = app_name or derive_app_name(project_name)
    try:
        adb = shutil.which("adb")
        with console.step("Checking for a connected device"):
            if adb is None:
                raise StepError("adb not on PATH (install Android platform-tools)")
            devices = connected_devices()
            if not devices:
                raise StepError("no ready device (connect one and run `adb devices`)")
            joined = ", ".join(devices)
            console.info(f"device: {joined}")
        # Build with the same Gradle-then-repackage fallback as `tempest build`:
        # if the Gradle toolchain is unavailable, repackage the prebuilt host
        # (shared id) so `run` still installs + launches something.
        try:
            apk = build_apk(
                app,
                app_id=resolved_id,
                app_name=resolved_name,
                version_name=app_version,
                version_code=version_code,
                console=console,
            )
        except (StepError, subprocess.CalledProcessError) as exc:
            reason = (
                f"exit {exc.returncode}"
                if isinstance(exc, subprocess.CalledProcessError)
                else str(exc)
            )
            console.info(
                f"Gradle build unavailable ({reason}) — falling back to the "
                "toolchain-free repackage. The APK keeps the shared id "
                "`org.tempestroid.host`."
            )
            apk = package_app_apk(app, version=__version__, console=console)
            resolved_id = "org.tempestroid.host"
        # The activity class lives in the fixed namespace; the package is the
        # per-app applicationId (or the shared host id after a fallback).
        host_activity = f"{resolved_id}/org.tempestroid.host.MainActivity"
        with console.step(f"Installing {apk.name}"):
            console.run_command([adb, "install", "-r", str(apk)])
        with console.step(f"Launching {host_activity}"):
            console.run_command([adb, "shell", "am", "start", "-n", host_activity])
        console.info("running on device. Streaming logs (Ctrl-C to stop).")
        subprocess.run([adb, "logcat", "-v", "tag"], check=False)  # noqa: S603
        return 0
    except StepError:
        return 1
    except FileNotFoundError as exc:
        console.fail(f"run failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def _run_uitest(path: str, target: str, jobs: int = 1) -> int:
    """Run a UI test file against a backend target and report the outcome.

    Args:
        path: Path to the UI test file (or a directory of ``test_*.py`` files for
            the emulator target).
        target: The backend target (``headless`` or ``emulator``).
        jobs: Emulator instances to run in parallel (``emulator`` only).

    Returns:
        ``0`` when every test passed, ``1`` otherwise (or on a load error).
    """
    if target == "emulator":
        return _run_uitest_emulator(path, jobs)
    from tempestroid.testing import run_test_file

    try:
        report = run_test_file(path, target=target)
    except NotImplementedError as exc:
        print(exc)
        return 1
    except (FileNotFoundError, AttributeError, TypeError, ValueError) as exc:
        print(f"cannot run UI tests: {exc}")
        return 1

    _print_report(report)
    return 0 if report.passed else 1


def _discover_test_files(path: str) -> list[str]:
    """Resolve a path to a list of UI test files.

    Args:
        path: A file path or a directory (scanned for ``test_*.py``).

    Returns:
        The matching file paths (a single-element list for a file).
    """
    from pathlib import Path

    target = Path(path)
    if target.is_dir():
        return sorted(str(p) for p in target.glob("test_*.py"))
    return [str(target)]


def _run_uitest_emulator(path: str, jobs: int) -> int:
    """Run UI tests on N real emulators, sharding files and capturing shots.

    Acquires up to ``jobs`` serials from an :class:`EmulatorPool` (reusing any
    already-running emulator), shards the discovered files across them, runs each
    on an :class:`EmulatorBackend`, saves a real screenshot per test under
    ``docs/assets/emulator/uitest/``, and aggregates the reports.

    Args:
        path: A UI test file or a directory of ``test_*.py`` files.
        jobs: Desired parallel emulator count (capped by hardware).

    Returns:
        ``0`` when every test passed, else ``1``.
    """
    from pathlib import Path

    from tempestroid.testing import EmulatorPool, run_test_files_emulator

    files = _discover_test_files(path)
    if not files:
        print(f"no UI test files found at {path}")
        return 1

    pool = EmulatorPool()
    serials = pool.allocate(jobs)
    if not serials:
        print(
            "no emulator available. Start one (`make emulator`) or connect a "
            "device, then retry."
        )
        return 1
    joined = ", ".join(serials)
    print(f"running {len(files)} file(s) on {len(serials)} emulator(s): {joined}")
    shot_dir = Path("docs/assets/emulator/uitest")
    try:
        reports = run_test_files_emulator(
            list(files), serials, screenshot_dir=shot_dir
        )
    finally:
        pool.teardown()

    all_passed = True
    for report in reports:
        _print_report(report)
        all_passed = all_passed and report.passed
    print(f"screenshots saved under {shot_dir}/")
    return 0 if all_passed else 1


def _print_report(report: TestReport) -> None:
    """Print one :class:`TestReport`'s outcomes in a uniform format.

    Args:
        report: A :class:`tempestroid.testing.TestReport`.
    """
    print(f"\n{report.path} (target {report.target!r}):")
    if not report.outcomes:
        print(f"  no `test_*` functions found in {report.path}")
        return
    for outcome in report.outcomes:
        mark = "PASS" if outcome.passed else "FAIL"
        print(f"  [{mark}] {outcome.name}")
        if not outcome.passed:
            print(f"    {outcome.message}")
            if outcome.traceback:
                indented = "\n".join(
                    f"      {line}"
                    for line in outcome.traceback.rstrip().splitlines()
                )
                print(indented)
            if outcome.tree_dump:
                print(f"    tree at failure:\n      {outcome.tree_dump}")
    passed = sum(1 for o in report.outcomes if o.passed)
    print(f"  {passed}/{len(report.outcomes)} passed.")


def _run_doctor(verbose: bool) -> int:
    """Probe the Android build/run prerequisites and report them.

    Build readiness (JDK + android-host + SDK) decides the exit code; a missing
    ``adb``/device is reported as informational, since ``build apk``/``prd`` need
    no device — only ``run``/``install``/``deploy`` do.

    Args:
        verbose: Show resolution hints for failed checks.

    Returns:
        ``0`` when the build prerequisites are satisfied, else ``1``.
    """
    from tempestroid.cli.console import Console
    from tempestroid.cli.packaging import preflight

    # Build needs JDK + android-host + SDK; adb/device are run-only.
    build_critical = {"jdk", "android-host", "android-sdk"}
    console = Console(verbose=verbose)
    console.info("tempest doctor — Android build/run prerequisites")

    build_ok = True
    for check in preflight(need_device=True):
        if check.ok:
            console.info(f"{check.name}: {check.detail}")
            continue
        if check.name in build_critical:
            build_ok = False
            console.fail(f"{check.name}: {check.detail}")
        else:
            # Run-only (adb/device): not a build blocker.
            console.info(f"{check.name}: {check.detail} (only for run/install)")
        if check.hint:
            console.info(f"  → {check.hint}")

    if build_ok:
        console.info("build prerequisites satisfied — ready to `tempest build`.")
        return 0
    console.fail("build prerequisites are missing (see above).")
    return 1


def _run_clean(include_keystore: bool) -> int:
    """Remove the rebuildable build caches under ``~/.tempestroid``.

    Args:
        include_keystore: Also delete the cached release keystore.

    Returns:
        ``0`` on success (an empty cache counts as success), ``1`` if a cache
        entry could not be removed.
    """
    from tempestroid.cli.console import Console
    from tempestroid.cli.release_build import clean_cache

    console = Console()
    try:
        removed = clean_cache(include_keystore=include_keystore)
    except OSError as exc:
        console.fail(f"could not clean the cache: {exc}")
        return 1
    if not removed:
        console.info("cache already clean — nothing to remove.")
        return 0
    for path in removed:
        console.info(f"removed {path}")
    console.info(f"cleaned {len(removed)} cache entries.")
    return 0


def _run_setup(install: bool, sdk_dir: str | None, verbose: bool) -> int:
    """Diagnose (and optionally install) the Android build environment.

    Args:
        install: Auto-install the Android SDK + NDK when ``True``.
        sdk_dir: SDK directory to inspect/install into, or ``None`` for the
            default.
        verbose: Echo raw commands and stream full subprocess output.

    Returns:
        The process exit code (``0`` when build-ready).
    """
    import subprocess
    from pathlib import Path

    from tempestroid.cli.console import Console, StepError
    from tempestroid.cli.packaging import ToolchainError
    from tempestroid.cli.setup_env import setup_build_env

    console = Console(verbose=verbose)
    try:
        return setup_build_env(
            sdk_dir=Path(sdk_dir) if sdk_dir else None,
            install=install,
            console=console,
        )
    except StepError:
        return 1
    except ToolchainError as exc:
        console.fail(f"setup failed: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        console.fail(f"setup command failed (exit {exc.returncode}).")
        return exc.returncode or 1


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested command.

    Thin wrapper around the Typer ``app`` that returns a process exit code
    instead of raising :class:`SystemExit`, so it stays usable both as the
    console-script entry point and from tests. Click runs in standalone mode,
    so help/version output and usage errors are printed for us; we only map the
    resulting :class:`SystemExit` to a returned exit code.

    Args:
        argv: Argument vector to parse. Defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    command = typer.main.get_command(app)
    try:
        command.main(args=argv, prog_name="tempest")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    app()
