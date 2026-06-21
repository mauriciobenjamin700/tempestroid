#!/usr/bin/env bash
# stage_science_x86.sh — add the scientific stack (scipy + scikit-learn) to the
# x86_64 device site-packages, on top of the base deps staged by 02_stage_deps.sh
# (TEMPEST_ABI=x86_64). This is the G6 payload: it is OPT-IN (heavy — scipy +
# sklearn + their deps add ~140 MB), so a normal x86_64 build never carries it.
#
# What it stages into toolchain/dist/site-packages-x86_64/:
#   1) the cross-compiled Android wheels (clang-only, ZERO Fortran — OpenBLAS
#      static-linked into scipy, NDK libomp vendored into sklearn), built by
#      toolchain/build_{openblas,scipy,sklearn}_x86.sh:
#        - scipy-*-android_*_x86_64.whl
#        - scikit_learn-*-android_*_x86_64.whl
#   2) the PURE-Python runtime deps of scikit-learn (platform-agnostic, so they
#      install straight from PyPI): joblib, threadpoolctl, narwhals.
#
# Prereqs: `make stage-x86` (or TEMPEST_ABI=x86_64 toolchain/02_stage_deps.sh) ran
# first, so numpy + pydantic + tempest-core are already in the staging dir, and
# build_scipy_x86.sh + build_sklearn_x86.sh produced the wheels under
# toolchain/dist/wheels-x86_64/.
#
# Usage: bash toolchain/stage_science_x86.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/toolchain/dist"
WHEELS="$DIST/wheels-x86_64"
STAGE="$DIST/site-packages-x86_64"

[ -d "$STAGE" ] || {
    echo "ERROR: $STAGE missing — run \`make stage-x86\` first." >&2
    exit 1
}

unzip_wheel() {
    local glob="$1" whl
    whl="$(ls "$WHEELS"/$glob 2>/dev/null | head -1 || true)"
    if [ -z "$whl" ] || [ ! -f "$whl" ]; then
        echo "ERROR: no wheel matching $glob under $WHEELS — run build_${glob%%-*}_x86.sh" >&2
        exit 1
    fi
    echo "==> unpacking $(basename "$whl")"
    python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
        "$whl" "$STAGE"
}

echo "==> staging the scientific stack into $STAGE"
unzip_wheel "scipy-*-android_*_x86_64.whl"
unzip_wheel "scikit_learn-*-android_*_x86_64.whl"

# scikit-learn's pure-Python runtime deps. These are py3-none-any (no native
# code), so a host `uv pip install --target` lands the correct files; --no-deps
# keeps it from dragging a host-platform numpy/scipy over the Android wheels.
echo "==> installing pure-Python sklearn deps (joblib, threadpoolctl, narwhals)"
uv pip install --target "$STAGE" --no-deps joblib threadpoolctl narwhals

# Drop dist-info + caches we never need on device (smaller APK), matching
# 02_stage_deps.sh. The Gradle CopyPythonSitePackagesTask additionally trims the
# scipy/sklearn test suites and renames .gz datasets at packaging time.
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -maxdepth 1 -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> staged science stack:"
for pkg in scipy sklearn joblib threadpoolctl narwhals; do
    [ -e "$STAGE/$pkg" ] || [ -e "$STAGE/$pkg.py" ] && echo "    + $pkg"
done
echo "==> done. Build with: make apk-x86 (the APK will be large — G7 trims it)."
