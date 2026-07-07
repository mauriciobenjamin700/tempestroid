#!/usr/bin/env bash
# build_numpy_x86.sh — back-compat shim: build the Android x86_64 numpy wheel.
#
# The recipe is now ABI-parametrized in build_numpy.sh (the three cross-compile
# blockers live there). This wrapper preserves the historical entry point (and
# `make stage-x86` / docs that name it) by delegating with the x86_64 ABI.
# For the arm64 device wheel use build_numpy_arm64.sh (or `build_numpy.sh arm64-v8a`).
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/build_numpy.sh" x86_64
