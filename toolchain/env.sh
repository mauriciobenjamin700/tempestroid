#!/usr/bin/env bash
# Shared environment for the Trilho B build scripts. Source it:
#   source toolchain/env.sh
#
# Override any of these before sourcing if your layout differs.

# --- Versions (reconfirm before building — the ecosystem moves fast) ---------
export TEMPEST_PYTHON_VERSION="${TEMPEST_PYTHON_VERSION:-3.14}"
export TEMPEST_NDK_VERSION="${TEMPEST_NDK_VERSION:-27.3.13750724}"   # NDK r27
export TEMPEST_ANDROID_API="${TEMPEST_ANDROID_API:-24}"             # 3.14 minimum
export TEMPEST_ABI="${TEMPEST_ABI:-arm64-v8a}"                       # aarch64
export TEMPEST_RUST_TARGET="${TEMPEST_RUST_TARGET:-aarch64-linux-android}"

# --- Toolchain locations -----------------------------------------------------
# This host installs the SDK system-wide at /usr/lib/android-sdk; override if
# your SDK lives elsewhere.
export ANDROID_HOME="${ANDROID_HOME_OVERRIDE:-/usr/lib/android-sdk}"
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/$TEMPEST_NDK_VERSION}"
# Make sure cargo + the SDK tools are on PATH for cibuildwheel/maturin.
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
export PATH="$ANDROID_HOME/platform-tools:$PATH"

# --- Output layout (consumed by ../android-host) -----------------------------
TEMPEST_TOOLCHAIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export TEMPEST_TOOLCHAIN_DIR
export TEMPEST_DIST_DIR="${TEMPEST_DIST_DIR:-$TEMPEST_TOOLCHAIN_DIR/dist}"
export TEMPEST_PYTHON_PREFIX="$TEMPEST_DIST_DIR/python"
export TEMPEST_WHEELS_DIR="$TEMPEST_DIST_DIR/wheels"

echo "tempest toolchain env:"
echo "  python=$TEMPEST_PYTHON_VERSION  ndk=$TEMPEST_NDK_VERSION  api=$TEMPEST_ANDROID_API  abi=$TEMPEST_ABI"
echo "  ANDROID_HOME=$ANDROID_HOME"
echo "  dist=$TEMPEST_DIST_DIR"
