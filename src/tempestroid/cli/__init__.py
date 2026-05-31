"""Command-line interface for tempestroid."""

from tempestroid.cli.app_loader import AppSpec, load_app_spec, spec_from_source
from tempestroid.cli.main import build_parser, main
from tempestroid.cli.packaging import android_host_dir, run_build, run_run
from tempestroid.cli.scaffold import scaffold_app

__all__ = [
    "build_parser",
    "main",
    "AppSpec",
    "load_app_spec",
    "spec_from_source",
    "scaffold_app",
    "run_build",
    "run_run",
    "android_host_dir",
]
