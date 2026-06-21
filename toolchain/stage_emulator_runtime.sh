#!/usr/bin/env bash
# stage_emulator_runtime.sh — stage the x86_64 CPython runtime for the headless
# emulator target (F7).
#
# A headless x86_64 Android emulator needs an x86_64 CPython prefix + x86_64
# site-packages, mirroring the arm64 device path but for the emulator ABI. This
# script reproduces the proven manual recipe:
#
#   1) Extract the official x86_64-linux-android CPython prefix from the
#      cibuildwheel cache tarball into dist/python/x86_64/ (no download — the
#      tarball is already there from a prior wheel build).
#   2) Stage the x86_64 site-packages via 02_stage_deps.sh with TEMPEST_ABI=x86_64
#      (→ dist/site-packages-x86_64/), which unpacks the x86_64 pydantic_core wheel
#      over the (arch-independent) pure-Python deps.
#
# The arm64 staging (dist/python/arm64-v8a + dist/site-packages) is never touched.
#
# Output:
#   dist/python/x86_64/{include,lib}            (CPython prefix, libpython3.14.so = ELF x86-64)
#   dist/site-packages-x86_64/                  (deps + x86_64 pydantic_core)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"
PY_VERSION="${TEMPEST_PYTHON_VERSION_FULL:-3.14.3}"
PREFIX_DST="$DIST/python/x86_64"

# The cibuildwheel cache holds the official Android x86_64 CPython tarball that
# 01_build_wheels.sh downloaded to build the x86_64 wheel. We reuse it (no fetch).
CACHE_TARBALL="${TEMPEST_X86_TARBALL:-$HOME/.cache/cibuildwheel/python-$PY_VERSION-x86_64-linux-android.tar.gz}"

echo "==> staging x86_64 CPython prefix at $PREFIX_DST"

if [[ ! -f "$CACHE_TARBALL" ]]; then
    cat >&2 <<EOF
ERROR: x86_64 CPython tarball not found:
  $CACHE_TARBALL

It is the official python.org Android release for x86_64-linux-android. It is
normally cached by cibuildwheel when 01_build_wheels.sh builds the x86_64 wheel.
To populate it:
  - run ./01_build_wheels.sh (which downloads + caches it), or
  - download python-$PY_VERSION-x86_64-linux-android.tar.gz from
    https://www.python.org/downloads/android/ into
    \$HOME/.cache/cibuildwheel/ (or point TEMPEST_X86_TARBALL at it).
EOF
    exit 1
fi

# The tarball ships a ./prefix/{include,lib} tree (same shape as the arm64 release).
# Extract only that prefix into dist/python/x86_64/ (idempotent: clear first).
rm -rf "$PREFIX_DST"
mkdir -p "$PREFIX_DST"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -xzf "$CACHE_TARBALL" -C "$tmp" ./prefix
cp -a "$tmp/prefix/include" "$PREFIX_DST/include"
cp -a "$tmp/prefix/lib" "$PREFIX_DST/lib"

echo "==> staged x86_64 prefix:"
ls -1 "$PREFIX_DST"
libpy="$PREFIX_DST/lib/libpython${TEMPEST_PYTHON_VERSION:-3.14}.so"
if [[ -f "$libpy" ]]; then
    file "$libpy" 2>/dev/null || true
fi

# Now stage the x86_64 site-packages (unchanged arm64 staging is untouched).
echo "==> staging x86_64 site-packages (TEMPEST_ABI=x86_64)"
TEMPEST_ABI=x86_64 "$HERE/02_stage_deps.sh"

echo "==> x86_64 emulator runtime staged. Build with:"
echo "    cd android-host && ./gradlew :app:assembleDebug \\"
echo "        -Ptempest.abi=x86_64 \\"
echo "        -Ptempest.pythonPrefix=../toolchain/dist/python/x86_64 \\"
echo "        -Ptempest.depsDir=../toolchain/dist/site-packages-x86_64"
