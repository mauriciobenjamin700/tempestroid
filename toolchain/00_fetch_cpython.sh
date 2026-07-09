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
    # Download the OFFICIAL python.org Android "embeddable prefix" for this ABI
    # and stage it into $TEMPEST_PYTHON_PREFIX/$TEMPEST_ABI/. Fully automated so
    # `tempest build --feature <x> --from-source` works from a clean install —
    # no manual tarball hunting (that was the old TODO that shipped an empty
    # prefix → CMake `fatal error: 'Python.h' file not found`).
    full="$TEMPEST_PYTHON_FULL_VERSION"
    case "$TEMPEST_ABI" in
        arm64-v8a) triple="aarch64-linux-android" ;;
        x86_64)    triple="x86_64-linux-android" ;;
        *)
            echo "ERROR: unsupported TEMPEST_ABI '$TEMPEST_ABI' (want arm64-v8a|x86_64)" >&2
            exit 2
            ;;
    esac
    dest="$TEMPEST_PYTHON_PREFIX/$TEMPEST_ABI"
    header="$dest/include/python${TEMPEST_PYTHON_VERSION}/Python.h"
    lib="$dest/lib/libpython${TEMPEST_PYTHON_VERSION}.so"

    # Idempotent: a complete prefix is already staged → nothing to do.
    if [ -f "$header" ] && [ -f "$lib" ]; then
        echo "==> CPython $full prefix already staged at $dest — skipping fetch"
        exit 0
    fi

    url="https://www.python.org/ftp/python/${full}/python-${full}-${triple}.tar.gz"
    cache="${TEMPEST_DOWNLOAD_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/tempestroid}"
    mkdir -p "$cache"
    tarball="$cache/python-${full}-${triple}.tar.gz"

    if [ ! -s "$tarball" ]; then
        echo "==> Downloading official CPython $full Android prefix ($triple)"
        echo "    $url"
        curl -fSL --retry 3 --retry-delay 2 -o "$tarball.part" "$url"
        mv "$tarball.part" "$tarball"
    else
        echo "==> Using cached tarball: $tarball"
    fi

    # The release unpacks to ./prefix/{include,lib,...} plus android.py helpers;
    # only the prefix/ subtree is the staged runtime + headers.
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    tar -xzf "$tarball" -C "$tmp"
    if [ ! -d "$tmp/prefix" ]; then
        echo "ERROR: unexpected tarball layout (no prefix/ in $tarball)" >&2
        exit 1
    fi
    mkdir -p "$dest"
    cp -a "$tmp/prefix/." "$dest/"

    # Validate: headers + interpreter present, and the .so is the right ABI.
    if [ ! -f "$header" ] || [ ! -f "$lib" ]; then
        echo "ERROR: staging incomplete — missing Python.h or libpython in $dest" >&2
        exit 1
    fi
    if command -v file >/dev/null 2>&1; then
        case "$triple" in
            aarch64-*) want="aarch64" ;;
            x86_64-*)  want="x86-64" ;;
        esac
        if ! file "$lib" | grep -qiE "$want"; then
            echo "ERROR: $lib is not a $want ELF (wrong-ABI tarball?)" >&2
            exit 1
        fi
    fi
    echo "==> Staged CPython $full ($triple) → $dest"
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
