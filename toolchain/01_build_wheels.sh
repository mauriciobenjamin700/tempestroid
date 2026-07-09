#!/usr/bin/env bash
# B1 (DERISK CRÍTICO) — cross-compile native wheels for Android.
#
# pydantic-core (Rust) has NO prebuilt Android wheel, so we build it with
# cibuildwheel >= 3.1 (Android support landed there in 3.1.0, Jul 2025).
# Pure-Python deps (pydantic, httpx, ...) need no build — pip resolves them.
#
# Output: $TEMPEST_WHEELS_DIR/*.whl  (tag: android_24_arm64_v8a)
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[ -z "${TEMPEST_DIST_DIR:-}" ] && source "$here/env.sh"
mkdir -p "$TEMPEST_WHEELS_DIR"

# --- preflight ---------------------------------------------------------------
command -v cibuildwheel >/dev/null || { echo "install cibuildwheel: uv tool install cibuildwheel" >&2; exit 1; }
[ -d "$ANDROID_HOME" ] || { echo "ANDROID_HOME not found: $ANDROID_HOME" >&2; exit 1; }
rustup target list --installed | grep -q "$TEMPEST_RUST_TARGET" \
    || { echo "rustup target add $TEMPEST_RUST_TARGET" >&2; exit 1; }

# --- cibuildwheel config -----------------------------------------------------
export CIBW_PLATFORM=android
export CIBW_ARCHS_ANDROID="${TEMPEST_ABI//-/_}"        # arm64-v8a -> arm64_v8a
export CIBW_BUILD="cp${TEMPEST_PYTHON_VERSION/./}-*"   # 3.14 -> cp314-*
export CIBW_BUILD_FRONTEND="build"                     # pip is NOT supported on Android

build_pkg() {
    local repo="$1" name="$2"
    local src="$here/.src/$name"
    [ -d "$src" ] || git clone --depth 1 "$repo" "$src"
    echo "==> cibuildwheel: $name"
    cibuildwheel --platform android --output-dir "$TEMPEST_WHEELS_DIR" "$src"
}

# The Rust crate — the fire test of the whole runtime (plan §2).
build_pkg "https://github.com/pydantic/pydantic-core" "pydantic-core"

# numpy (C extension, no prebuilt Android wheel) — a hard dependency of the
# vision stack (ort_vision_sdk). Its ABI-parametrized recipe lives in
# build_numpy.sh; the wheel lands in dist/wheels-<abi>/, where 02_stage_deps.sh
# (TEMPEST_VISION=1) picks it up. Building it here means `--feature vision
# --from-source` gets numpy for ANY target ABI automatically — previously only
# the x86_64 wheel was ever built by hand, so arm64 vision APKs shipped without
# numpy and inference died on device with `No module named 'numpy'`.
echo "==> building numpy Android wheel ($TEMPEST_ABI)"
"$here/build_numpy.sh" "$TEMPEST_ABI"

echo
echo "Wheels in $TEMPEST_WHEELS_DIR:"
ls -1 "$TEMPEST_WHEELS_DIR" 2>/dev/null || true
echo
echo "Done-when: import pydantic works on an arm64 device/emulator."
echo "Reconfirm cibuildwheel/maturin versions before trusting this (see runbook)."
