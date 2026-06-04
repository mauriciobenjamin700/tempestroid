"""Command-line interface for tempestroid."""

from typing import TYPE_CHECKING, Any

from tempestroid.cli.app_loader import (
    AppSpec,
    load_app_spec,
    spec_from_project,
    spec_from_source,
)
from tempestroid.cli.bundle import (
    MANIFEST_NAME,
    ProjectLayout,
    build_bundle,
    bundle_hash,
    extract_bundle,
    resolve_project,
    tree_signature,
)
from tempestroid.cli.console import Console, StepError
from tempestroid.cli.packaging import (
    PreflightCheck,
    ToolchainError,
    adb_reverse,
    build_apk,
    bundled_host_apk,
    connected_devices,
    deploy_offline,
    find_android_host,
    host_apk_url,
    host_installed,
    install_host,
    launch_host_dev,
    preflight,
    report_preflight,
    resolve_host_apk,
    run_on_device,
    stage_app_source,
)
from tempestroid.cli.project import AppResolutionError, resolve_app
from tempestroid.cli.scaffold import (
    DEFAULT_APP_TEMPLATE,
    ScaffoldResult,
    scaffold,
)
from tempestroid.cli.setup_env import (
    install_android_sdk,
    probe_build_env,
    setup_build_env,
)

if TYPE_CHECKING:
    from tempestroid.cli.main import app, main

__all__ = [
    "app",
    "main",
    "AppSpec",
    "load_app_spec",
    "spec_from_project",
    "spec_from_source",
    "MANIFEST_NAME",
    "ProjectLayout",
    "build_bundle",
    "bundle_hash",
    "tree_signature",
    "extract_bundle",
    "resolve_project",
    "scaffold",
    "ScaffoldResult",
    "DEFAULT_APP_TEMPLATE",
    "AppResolutionError",
    "resolve_app",
    "install_android_sdk",
    "probe_build_env",
    "setup_build_env",
    "Console",
    "StepError",
    "ToolchainError",
    "PreflightCheck",
    "adb_reverse",
    "build_apk",
    "bundled_host_apk",
    "connected_devices",
    "deploy_offline",
    "find_android_host",
    "host_apk_url",
    "host_installed",
    "install_host",
    "launch_host_dev",
    "preflight",
    "report_preflight",
    "resolve_host_apk",
    "run_on_device",
    "stage_app_source",
]


def __getattr__(name: str) -> Any:  # noqa: ANN401 — PEP 562 module hook returns Any
    """Lazily expose the Typer ``app``/``main`` entry points.

    Importing them eagerly would pull in ``typer``, which the Android device
    runtime does not bundle — yet the device's code-push client imports
    :func:`spec_from_source` from this package, which runs this ``__init__``.
    Deferring the ``main`` import keeps ``tempestroid.cli.app_loader``
    importable without ``typer`` (so ``tempest serve`` works on device) while
    still exposing ``tempestroid.cli.app`` / ``main`` on the desktop.

    Args:
        name: The attribute being accessed.

    Returns:
        The requested Typer entry point.

    Raises:
        AttributeError: If ``name`` is not a deferred CLI entry point.
    """
    if name in {"app", "main"}:
        import importlib

        module = importlib.import_module("tempestroid.cli.main")
        # Bind both entry points into the package namespace so they shadow the
        # ``main`` submodule (as the original eager re-export did) and memoize:
        # later accesses resolve as real attributes without re-entering here.
        globals()["app"] = module.app
        globals()["main"] = module.main
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
