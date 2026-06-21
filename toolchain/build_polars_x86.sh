#!/usr/bin/env bash
# G — cross-compile Polars (polars-runtime-32) as an Android x86_64 wheel.
#
# Polars is Rust/maturin — the SAME class as pydantic-core (B1), which cibuildwheel
# already cross-compiles to Android (it provisions the Rust android target + the
# NDK linker). We build the `polars-runtime-32` sdist (the Rust core; `polars`
# itself is a pure-Python wrapper). Output is `abi3`, so ONE wheel serves every
# CPython >= 3.10.
#
# Two Android blockers, both handled by editing the unpacked sdist:
#   1) the sdist pins `rust-toolchain.toml` to a specific NIGHTLY, and its default
#      feature set includes `nightly` (SIMD via `#![feature(...)]`). We drop the
#      pin (use cibuildwheel's stable Rust) and drop the `nightly` feature.
#   2) the default feature `full` pulls `fast_alloc` -> tikv-jemallocator/mimalloc
#      (don't build for *-linux-android) and `clipboard` -> arboard (needs X11).
#      We override the runtime crate's `default` to a curated IO + core set:
#      csv/parquet/ipc/json + sql/performant/trigonometry — no nightly, no
#      fast_alloc (system allocator), no clipboard, no cloud client.
#
# Output: toolchain/dist/wheels-x86_64/polars_runtime_32-*-abi3-android_*_x86_64.whl
#
# Prereqs: Android SDK/NDK r27, cibuildwheel >= 4.0, a Rust toolchain on PATH.
# Does NOT run in WSL without the Android toolchain.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/.src"
out="$here/dist/wheels-x86_64"
polars_version="${POLARS_VERSION:-1.41.2}"
ndk="${ANDROID_NDK_ROOT:-/usr/lib/android-sdk/ndk/27.3.13750724}"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_NDK_ROOT="$ndk" ANDROID_NDK_HOME="$ndk"

command -v cibuildwheel >/dev/null || { echo "install cibuildwheel >= 4.0" >&2; exit 1; }
command -v cargo >/dev/null || { echo "Rust toolchain (cargo) not on PATH" >&2; exit 1; }
[ -d "$ndk" ] || { echo "NDK not found: $ndk" >&2; exit 1; }
mkdir -p "$src" "$out"

pkg="polars_runtime_32-$polars_version"
pd_src="$src/$pkg"
if [ ! -d "$pd_src" ]; then
    echo "==> fetching polars-runtime-32 $polars_version sdist"
    url="$(curl -sL --max-time 60 "https://pypi.org/pypi/polars-runtime-32/$polars_version/json" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print([f['url'] for f in d['urls'] if f['packagetype']=='sdist'][0])")"
    [ -n "$url" ] || { echo "ERROR: could not resolve sdist URL (network?)" >&2; exit 1; }
    curl -sL --max-time 300 --retry 3 "$url" -o "$src/$pkg.tar.gz"
    tar xzf "$src/$pkg.tar.gz" -C "$src"
fi

# Blocker 1: drop the nightly toolchain pin -> use cibuildwheel's stable Rust.
rm -f "$pd_src/rust-toolchain.toml"

# Blocker 1+2: replace the runtime crate's default features. Use the COHERENT
# `full_functionality` set (a curated IO subset breaks the polars-python match
# statements over IRFunctionExpr/IRStringFunction/... which require the full
# variant coverage), but drop the two Android-hostile parts: `nightly` (SIMD via
# unstable rustc) and `fast_alloc` (jemalloc/mimalloc, don't build for android).
# Also drop `clipboard` (arboard needs X11, no android backend). `polars-python/
# full_functionality` still pulls `polars_cloud_client` — kept (pure network, no
# GUI); strip it here too if it turns out not to cross-compile.
rt_cargo="$pd_src/py-polars/runtime/polars-runtime-32/Cargo.toml"
android_default='default = ["ffi_plugin", "csv", "object", "sql", "trigonometry", "parquet", "ipc", "catalog", "polars-python/full_functionality", "performant"]'
sed -i -E "s|^default = \[\"full\", \"nightly\"\]|$android_default|" "$rt_cargo"
echo "==> runtime default features now:"; grep -m1 "^default = " "$rt_cargo"

# polars-python's `io` feature pulls `clipboard` -> arboard, which has no Android
# backend (`cannot find Clipboard in platform`). Drop the enabling line (the
# `clipboard = ["arboard"]` feature DEF stays, just never enabled); read/write to
# the system clipboard isn't a device DataFrame need.
pp_cargo="$pd_src/crates/polars-python/Cargo.toml"
sed -i -E '/^[[:space:]]*"clipboard",[[:space:]]*$/d' "$pp_cargo"
echo "==> clipboard enable removed from polars-python io feature"

# Drop the `cpython-freethreading` enable group cibuildwheel 4.x rejects (idempotent).
sed -i -E 's/^enable = \[[^]]*cpython-freethreading[^]]*\]/enable = ["cpython-prerelease"]/' \
    "$pd_src/pyproject.toml" 2>/dev/null || true

# Strip debug symbols at link time: an unstripped polars core .so is ~2.4 GB
# (debug info from the huge Rust workspace) — it both blows the APK and exceeds
# the 2 GB Java-array limit of AGP's asset compressor ("Required array size too
# large"). Stripped it is ~200 MB. cargo reads CARGO_PROFILE_<profile>_STRIP.
export CARGO_PROFILE_RELEASE_STRIP=symbols

export CIBW_PLATFORM=android
# cibuildwheel's Android runtime is CPython 3.14; the wheel maturin emits is abi3,
# so building on cp314 still yields a single cp310-abi3 wheel for all 3.10+.
export CIBW_BUILD="cp314-*"
export CIBW_BUILD_FRONTEND="build"
export CIBW_BEFORE_BUILD=""
export CIBW_TEST_SKIP="*"

echo "==> cibuildwheel: polars-runtime-32 $polars_version (android x86_64, stable, no fast_alloc)"
cibuildwheel --platform android --archs x86_64 --output-dir "$out" "$pd_src"

echo
echo "Wheel(s) in $out:"
ls -1 "$out"/polars_runtime_32-*-android_*_x86_64.whl
