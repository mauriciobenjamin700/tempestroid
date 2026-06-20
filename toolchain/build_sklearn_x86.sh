#!/usr/bin/env bash
# G6 — attempt to cross-compile scikit-learn as an Android x86_64 wheel.
#
# sklearn is Cython + C++ + OpenMP and depends on scipy. With scipy now building
# (build_scipy_x86.sh) the remaining sklearn-specific risk is OpenMP: the NDK ships
# `libomp` (LLVM OpenMP) under .../lib/clang/<v>/lib/linux/<arch>/, and clang's
# `-fopenmp` links it. sklearn's meson does `dependency('OpenMP', required: false)`
# and merely warns if absent (it can build single-threaded), so even if meson can't
# autodetect OpenMP across the cross-boundary, the build still completes.
#
# sklearn's meson skips ALL build-dep version checks when meson.is_cross_build()
# is true (see sklearn/meson.build), so the host scipy/numpy/cython versions don't
# need to match the Android wheels — only numpy *headers* are consumed (same cross
# path scipy used). The Android scipy/numpy wheels are runtime deps, staged on the
# device, not needed in the host build env.
#
# Output: toolchain/dist/wheels-x86_64/scikit_learn-*-cp314-cp314-android_26_x86_64.whl
#
# Prereqs: build_scipy_x86.sh + build_numpy_x86.sh ran (their wheels staged),
# Android SDK/NDK r27, cibuildwheel >= 4.0. Does NOT run in WSL without the NDK.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/.src"
out="$here/dist/wheels-x86_64"
sklearn_version="${SKLEARN_VERSION:-1.9.0}"
ndk="${ANDROID_NDK_ROOT:-/usr/lib/android-sdk/ndk/27.3.13750724}"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_NDK_ROOT="$ndk" ANDROID_NDK_HOME="$ndk"
# scipy required an API-26 floor (clog/cpow); keep sklearn consistent.
export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-26}"

# --- preflight ---------------------------------------------------------------
command -v cibuildwheel >/dev/null || { echo "install cibuildwheel >= 4.0" >&2; exit 1; }
[ -d "$ndk" ] || { echo "NDK not found: $ndk" >&2; exit 1; }
mkdir -p "$src" "$out"

# --- scikit-learn source -----------------------------------------------------
sk_src="$src/scikit_learn-$sklearn_version"
if [ ! -d "$sk_src" ]; then
    echo "==> fetching scikit-learn $sklearn_version sdist"
    url="$(python3 -c "import urllib.request,json; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/scikit-learn/$sklearn_version/json')); print([f['url'] for f in d['urls'] if f['packagetype']=='sdist'][0])")"
    curl -sL "$url" -o "$src/scikit_learn-$sklearn_version.tar.gz"
    tar xzf "$src/scikit_learn-$sklearn_version.tar.gz" -C "$src"
fi

# Long-double cross-prop (same as scipy/numpy — affects only host run-checks).
cross="$src/sklearn-cross-props.ini"
cat > "$cross" <<'EOF'
[properties]
longdouble_format = 'INTEL_EXTENDED_16_BYTES_LE'
EOF

# --- cibuildwheel config -----------------------------------------------------
export CIBW_PLATFORM=android
export CIBW_BUILD="cp${TEMPEST_PYTHON_VERSION:-3.14}-*"
export CIBW_BUILD="${CIBW_BUILD/./}"                 # cp3.14 -> cp314
export CIBW_BUILD_FRONTEND="build"
export CIBW_BEFORE_BUILD=""
export CIBW_TEST_SKIP="*"
export CIBW_CONFIG_SETTINGS="setup-args=--cross-file=$cross"
# Hand the NDK libomp to clang explicitly so -fopenmp resolves across the cross.
tc="$ndk/toolchains/llvm/prebuilt/linux-x86_64"
omp_dir="$tc/lib/clang/18/lib/linux/x86_64"
export CIBW_ENVIRONMENT="\
PIP_FIND_LINKS=$out \
LDFLAGS='-L$omp_dir' \
CFLAGS='-fopenmp' \
CXXFLAGS='-fopenmp'"

echo "==> cibuildwheel: scikit-learn $sklearn_version (android x86_64)"
cibuildwheel --platform android --archs x86_64 --output-dir "$out" "$sk_src"

echo
echo "Wheel(s) in $out:"
ls -1 "$out"/scikit_learn-*-android_*_x86_64.whl 2>/dev/null || echo "(no scikit-learn wheel produced)"
