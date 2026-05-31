#!/usr/bin/env bash
# B0 — obtain CPython for aarch64-linux-android.
#
# Two paths:
#   (default) download the OFFICIAL Android binary release from python.org
#   (custom)  cross-build from source with CPython's own Android/android.py
#
# Output: $TEMPEST_PYTHON_PREFIX/<abi>/ with lib/libpython3.14.so + lib/python3.14/
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[ -z "${TEMPEST_DIST_DIR:-}" ] && source "$here/env.sh"

mode="${1:-official}"
mkdir -p "$TEMPEST_PYTHON_PREFIX/$TEMPEST_ABI"

case "$mode" in
official)
    echo "==> Fetching official CPython $TEMPEST_PYTHON_VERSION Android release"
    echo "    Browse: https://www.python.org/downloads/android/"
    echo "    Pick the aarch64 tarball for $TEMPEST_PYTHON_VERSION.x and unpack into:"
    echo "      $TEMPEST_PYTHON_PREFIX/$TEMPEST_ABI/"
    echo
    echo "    The release ships a 'prefix' tree:"
    echo "      lib/libpython${TEMPEST_PYTHON_VERSION}.so      (interpreter, → jniLibs)"
    echo "      lib/lib*_python.so                              (bundled C deps, → jniLibs)"
    echo "      lib/python${TEMPEST_PYTHON_VERSION}/            (stdlib, → assets)"
    echo
    echo "    TODO: when the exact URL/filename is pinned, wire curl here. Left manual"
    echo "    on purpose so the version is reconfirmed (see android-runbook.md)."
    ;;
custom)
    echo "==> Custom cross-build via CPython Android/android.py"
    src="${TEMPEST_CPYTHON_SRC:-$here/.cpython}"
    if [ ! -d "$src" ]; then
        git clone --branch "$TEMPEST_PYTHON_VERSION" --depth 1 \
            https://github.com/python/cpython "$src"
    fi
    # android.py installs the pinned NDK via sdkmanager and does a two-stage
    # (build + host) cross-compile.
    ( cd "$src" && ./android.py build "$TEMPEST_RUST_TARGET" )
    ( cd "$src" && ./android.py package "$TEMPEST_RUST_TARGET" )
    echo "    Release tarball under: $src/cross-build/$TEMPEST_RUST_TARGET/dist"
    echo "    Unpack its prefix into $TEMPEST_PYTHON_PREFIX/$TEMPEST_ABI/"
    ;;
*)
    echo "usage: $0 [official|custom]" >&2
    exit 2
    ;;
esac
