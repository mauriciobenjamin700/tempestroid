"""Command-line interface for tempestroid."""

from tempestroid.cli.app_loader import AppSpec, load_app_spec, spec_from_source
from tempestroid.cli.console import Console, StepError
from tempestroid.cli.main import build_parser, main
from tempestroid.cli.packaging import (
    PreflightCheck,
    ToolchainError,
    build_apk,
    connected_devices,
    find_android_host,
    preflight,
    report_preflight,
    run_on_device,
    stage_app_source,
)
from tempestroid.cli.scaffold import DEFAULT_APP_TEMPLATE, scaffold

__all__ = [
    "build_parser",
    "main",
    "AppSpec",
    "load_app_spec",
    "spec_from_source",
    "scaffold",
    "DEFAULT_APP_TEMPLATE",
    "Console",
    "StepError",
    "ToolchainError",
    "PreflightCheck",
    "build_apk",
    "connected_devices",
    "find_android_host",
    "preflight",
    "report_preflight",
    "run_on_device",
    "stage_app_source",
]
