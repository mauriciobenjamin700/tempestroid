#!/usr/bin/env bash
# build_numpy_arm64.sh — build the Android arm64-v8a numpy wheel (device target).
#
# Thin wrapper over the ABI-parametrized build_numpy.sh. The only arch-specific
# knob is the long-double format (aarch64 = 128-bit IEEE quad -> IEEE_QUAD_LE);
# everything else (noblas, the Meson cross-file, the cibuildwheel >= 4.0 fix for
# the $(BLDLIBRARY) leak) is shared with the x86_64 recipe.
#
# Output: toolchain/dist/wheels-arm64-v8a/numpy-*-android_*_arm64_v8a.whl
# (02_stage_deps.sh with TEMPEST_ABI=arm64-v8a picks it up automatically).
#
# Prereqs: Android SDK/NDK r27 + cibuildwheel >= 4.0. Does NOT run in WSL without
# the Android toolchain.
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/build_numpy.sh" arm64-v8a
