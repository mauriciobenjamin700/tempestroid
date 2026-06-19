#!/usr/bin/env bash
# G1 — cross-compile numpy as an Android x86_64 wheel (emulator target).
#
# numpy has NO prebuilt Android wheel on PyPI, so we build it with cibuildwheel,
# mirroring the B1 pattern (pydantic-core). Unlike pydantic-core (Rust/maturin),
# numpy is a C/Cython/Meson extension and hit three cross-compile blockers — all
# captured here so the build is reproducible (see docs/research/g0-feasibility.md):
#
#   1. numpy's `before-build` hook provisions OpenBLAS via a host-only script that
#      isn't in the sdist and has no Android variant -> we skip it (CIBW_BEFORE_BUILD="")
#      and build BLAS-less with `-Dallow-noblas=true`. Fine for inference pre/post
#      (elementwise + small dot); revisit OpenBLAS-for-Android if heavy linalg is needed.
#   2. numpy's Meson does a `cc.run()` long-double probe that can't execute a target
#      binary when cross-compiling -> supply the value via a Meson cross-file property
#      (`longdouble_format`); x86_64 == 80-bit extended, 16-byte ('INTEL_EXTENDED_16_BYTES_LE').
#   3. The link step leaked an unexpanded `$(BLDLIBRARY)` from the Android CPython
#      sysconfig on cibuildwheel 3.4.1 -> FIXED by cibuildwheel >= 4.0 (Android matured).
#      This script therefore REQUIRES cibuildwheel >= 4.0.
#
# Also: cibuildwheel 4.x dropped the `cpython-freethreading` enable group numpy's
# pyproject lists, and numpy's test phase tries to `pip install` on the target -> we
# strip the stale enable group and skip tests (CIBW_TEST_SKIP="*").
#
# Output: toolchain/dist/wheels-x86_64/numpy-*-cp314-cp314-android_24_x86_64.whl
#
# Prereqs: Android SDK/NDK r27 (ANDROID_SDK_ROOT=/usr/lib/android-sdk on this host),
# cibuildwheel >= 4.0 (`uv tool install cibuildwheel` / `uv tool upgrade cibuildwheel`).
# Does NOT run in WSL without the Android toolchain.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/.src"
out="$here/dist/wheels-x86_64"
numpy_version="${NUMPY_VERSION:-2.4.6}"
ndk="${ANDROID_NDK_ROOT:-/usr/lib/android-sdk/ndk/27.3.13750724}"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_NDK_ROOT="$ndk" ANDROID_NDK_HOME="$ndk"

# --- preflight ---------------------------------------------------------------
command -v cibuildwheel >/dev/null || { echo "install cibuildwheel >= 4.0: uv tool install cibuildwheel" >&2; exit 1; }
[ -d "$ANDROID_SDK_ROOT" ] || { echo "ANDROID_SDK_ROOT not found: $ANDROID_SDK_ROOT" >&2; exit 1; }
[ -d "$ndk" ] || { echo "NDK not found: $ndk" >&2; exit 1; }
mkdir -p "$src" "$out"

# --- numpy source ------------------------------------------------------------
np_src="$src/numpy-$numpy_version"
if [ ! -d "$np_src" ]; then
    echo "==> fetching numpy $numpy_version sdist"
    url="$(python3 -c "import urllib.request,json; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/numpy/$numpy_version/json')); print([f['url'] for f in d['urls'] if f['packagetype']=='sdist'][0])")"
    curl -sL "$url" -o "$src/numpy-$numpy_version.tar.gz"
    tar xzf "$src/numpy-$numpy_version.tar.gz" -C "$src"
fi

# Blocker 3 follow-up: drop the `cpython-freethreading` enable group cibuildwheel
# 4.x no longer recognizes (idempotent).
sed -i 's/enable = \["cpython-freethreading", "pypy", "cpython-prerelease"\]/enable = ["pypy", "cpython-prerelease"]/' \
    "$np_src/pyproject.toml" || true

# Blocker 2: Meson cross-file supplying the long-double format (x86_64).
cross="$src/numpy-cross-props.ini"
cat > "$cross" <<'EOF'
[properties]
longdouble_format = 'INTEL_EXTENDED_16_BYTES_LE'
EOF

# --- cibuildwheel config -----------------------------------------------------
export CIBW_PLATFORM=android
export CIBW_BUILD="cp${TEMPEST_PYTHON_VERSION:-3.14}-*"
export CIBW_BUILD="${CIBW_BUILD/./}"                 # cp3.14 -> cp314
export CIBW_BUILD_FRONTEND="build"
export CIBW_BEFORE_BUILD=""                          # blocker 1: skip OpenBLAS host hook
export CIBW_TEST_SKIP="*"                            # can't pip-install on the target
export CIBW_CONFIG_SETTINGS="setup-args=-Dallow-noblas=true setup-args=--cross-file=$cross"

echo "==> cibuildwheel: numpy $numpy_version (android x86_64, noblas)"
cibuildwheel --platform android --archs x86_64 --output-dir "$out" "$np_src"

echo
echo "Wheel(s) in $out:"
ls -1 "$out"/numpy-*-android_*_x86_64.whl
