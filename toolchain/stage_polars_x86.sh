#!/usr/bin/env bash
# stage_polars_x86.sh — add Polars to the x86_64 device site-packages, on top of
# the base deps staged by 02_stage_deps.sh. OPT-IN (the Rust core .so is large).
#
# Polars 1.41 is split: `polars` is a pure-Python wrapper that imports the Rust
# core from `polars-runtime-32` (its only required dep). So we stage:
#   1) the cross-compiled `polars-runtime-32` Android wheel (build_polars_x86.sh,
#      abi3 -> one wheel for all CPython >=3.10);
#   2) the `polars` pure-Python wrapper (py3-none-any, from PyPI).
# numpy/pandas/pyarrow are OPTIONAL extras — not staged; the core reads/writes
# CSV/JSON/Parquet natively.
#
# Prereqs: `make stage-x86` ran, and build_polars_x86.sh produced the runtime wheel
# under toolchain/dist/wheels-x86_64/.
#
# Usage: bash toolchain/stage_polars_x86.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/toolchain/dist"
WHEELS="$DIST/wheels-x86_64"
STAGE="$DIST/site-packages-x86_64"
POLARS_VERSION="${POLARS_VERSION:-1.41.2}"

[ -d "$STAGE" ] || {
    echo "ERROR: $STAGE missing — run \`make stage-x86\` first." >&2
    exit 1
}

# Highest matching runtime wheel (abi3).
WHEEL="$(ls "$WHEELS"/polars_runtime_32-*-android_*_x86_64.whl 2>/dev/null | sort -V | tail -1 || true)"
if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then
    echo "ERROR: no polars-runtime-32 Android wheel under $WHEELS — run build_polars_x86.sh" >&2
    exit 1
fi

echo "==> unpacking $(basename "$WHEEL")"
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$WHEEL" "$STAGE"

# The pure-Python `polars` wrapper (py3-none-any). --no-deps so it doesn't try to
# pull a host polars-runtime-32 over the Android one we just staged.
echo "==> installing the polars wrapper (polars==$POLARS_VERSION, pure-Python)"
uv pip install --target "$STAGE" --no-deps "polars==$POLARS_VERSION"

find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -maxdepth 1 -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> staged Polars:"
for pkg in polars _polars_runtime_32; do
    [ -e "$STAGE/$pkg" ] && echo "    + $pkg"
done
echo "==> done. Build with: make apk-x86 (the APK will be large — G7 trims it)."
