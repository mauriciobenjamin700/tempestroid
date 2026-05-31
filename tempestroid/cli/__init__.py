"""Command-line interface for tempestroid."""

from tempestroid.cli.app_loader import AppSpec, load_app_spec, spec_from_source
from tempestroid.cli.console import Console, StepError
from tempestroid.cli.main import app, main
from tempestroid.cli.packaging import (
    PreflightCheck,
    ToolchainError,
    adb_reverse,
    build_apk,
    bundled_host_apk,
    connected_devices,
    find_android_host,
    host_apk_url,
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

__all__ = [
    "app",
    "main",
    "AppSpec",
    "load_app_spec",
    "spec_from_source",
    "scaffold",
    "ScaffoldResult",
    "DEFAULT_APP_TEMPLATE",
    "AppResolutionError",
    "resolve_app",
    "Console",
    "StepError",
    "ToolchainError",
    "PreflightCheck",
    "adb_reverse",
    "build_apk",
    "bundled_host_apk",
    "connected_devices",
    "find_android_host",
    "host_apk_url",
    "install_host",
    "launch_host_dev",
    "preflight",
    "report_preflight",
    "resolve_host_apk",
    "run_on_device",
    "stage_app_source",
]
