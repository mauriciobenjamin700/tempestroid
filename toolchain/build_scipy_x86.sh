#!/usr/bin/env bash
# G6 — attempt to cross-compile scipy as an Android x86_64 wheel (emulator target).
#
# This mirrors the numpy recipe (build_numpy_x86.sh) but scipy is harder: it needs
# a full BLAS *and* LAPACK (no `allow-noblas` escape), and historically a Fortran
# compiler. Two upstream changes make a clang-only Android build plausible in 2026:
#
#   1. scipy's FORTRAN inventory (scipy#18566) is CLOSED — every Fortran subpackage
#      was ported to C or deprecated. The ONLY remaining Fortran is `scipy.odr`
#      (odrpack/*.f). The `-D_without-fortran=true` meson option (scipy 1.16+) drops
#      `scipy.odr` and never adds Fortran as a language, so NO Fortran compiler is
#      needed to build the rest of scipy. (Verified in the 1.18.0 sdist: only
#      scipy/odr/odrpack/*.f and an optional HiGHS .f90 remain.)
#   2. OpenBLAS builds an f2c-machine-translated LAPACK ("C_LAPACK") with clang only
#      (NOFORTRAN=1) — see build_openblas_x86.sh. scipy links it as plain
#      libblas/liblapack via `-Duse-g77-abi=false` (default when fortran-free).
#
# So the Fortran "calcanhar" reduces to: (a) build OpenBLAS+C_LAPACK (done by
# build_openblas_x86.sh) and (b) point scipy's meson at it via pkg-config while
# disabling Fortran. This script does (b) on top of (a).
#
# Output: toolchain/dist/wheels-x86_64/scipy-*-cp314-cp314-android_24_x86_64.whl
#
# Prereqs: build_openblas_x86.sh ran first (dist/openblas-x86_64/), the numpy wheel
# staged (build_numpy_x86.sh), Android SDK/NDK r27, cibuildwheel >= 4.0.
# Does NOT run in WSL without the Android toolchain.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/.src"
out="$here/dist/wheels-x86_64"
openblas_dir="$here/dist/openblas-x86_64"
scipy_version="${SCIPY_VERSION:-1.18.0}"
ndk="${ANDROID_NDK_ROOT:-/usr/lib/android-sdk/ndk/27.3.13750724}"
# scipy.special's complex math (clog/cpow/cexp) is declared by Bionic only from
# API 26 (`__INTRODUCED_IN(26)`); building against API 24 hides them and clang
# errors on the implicit declaration. So scipy needs an API-26 floor (the emulator
# is API 34, so this is safe). numpy built fine at 24 because it ships its own
# npy_math complex; scipy dropped npymath and uses platform <complex.h>.
export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-26}"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_NDK_ROOT="$ndk" ANDROID_NDK_HOME="$ndk"

# --- preflight ---------------------------------------------------------------
command -v cibuildwheel >/dev/null || { echo "install cibuildwheel >= 4.0" >&2; exit 1; }
[ -d "$ndk" ] || { echo "NDK not found: $ndk" >&2; exit 1; }
[ -f "$openblas_dir/lib/pkgconfig/openblas.pc" ] || {
    echo "OpenBLAS not staged — run build_openblas_x86.sh first" >&2; exit 1; }
mkdir -p "$src" "$out"

# --- scipy source ------------------------------------------------------------
sp_src="$src/scipy-$scipy_version"
if [ ! -d "$sp_src" ]; then
    echo "==> fetching scipy $scipy_version sdist"
    url="$(python3 -c "import urllib.request,json; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/scipy/$scipy_version/json')); print([f['url'] for f in d['urls'] if f['packagetype']=='sdist'][0])")"
    curl -sL "$url" -o "$src/scipy-$scipy_version.tar.gz"
    tar xzf "$src/scipy-$scipy_version.tar.gz" -C "$src"
fi

# scipy ships an openblas/lapack provider via the `scipy-openblas` host hook, with
# no Android variant (same as numpy's). Skip it; we provide OpenBLAS ourselves.
sed -i 's/enable = \[\("cpython-freethreading", \)\?"pypy", "cpython-prerelease"\]/enable = ["pypy", "cpython-prerelease"]/' \
    "$sp_src/pyproject.toml" 2>/dev/null || true

# Patch: boost.math fp_traits keys long-double layout on the CPU macro and assumes
# x86_64 == 80-bit Intel-extended (LDBL_MANT_DIG==64). Android x86_64 (Bionic) uses
# 128-bit IEEE quad (LDBL_MANT_DIG==113) — same as Android arm64 — so the x86 branch
# fires a hard static_assert. Guard the x86 80-bit branch with `&& LDBL_MANT_DIG==64`
# so the quad case falls through to boost's IEEE-128 branch. (arm64 is unaffected:
# no __x86_64__ there, so it already reaches the 128-bit branch.)
boost_fp="$sp_src/subprojects/boost_math/math/include/boost/math/special_functions/detail/fp_traits.hpp"
if [ -f "$boost_fp" ] && ! grep -q "&& (LDBL_MANT_DIG == 64)" "$boost_fp"; then
    python3 - "$boost_fp" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = ("#elif defined(__i386) || defined(__i386__) || defined(_M_IX86) \\\n"
       "    || defined(__amd64) || defined(__amd64__)  || defined(_M_AMD64) \\\n"
       "    || defined(__x86_64) || defined(__x86_64__) || defined(_M_X64)\n")
new = ("#elif (defined(__i386) || defined(__i386__) || defined(_M_IX86) \\\n"
       "    || defined(__amd64) || defined(__amd64__)  || defined(_M_AMD64) \\\n"
       "    || defined(__x86_64) || defined(__x86_64__) || defined(_M_X64)) \\\n"
       "    && (LDBL_MANT_DIG == 64)\n")
assert old in s, "boost guard anchor not found"
open(p, "w").write(s.replace(old, new))
print("patched boost fp_traits x86 long-double guard")
PY
fi

# Patch: ducc0 (scipy's FFT backend) guards CPU-affinity calls with
# `defined(__linux__) && defined(_GNU_SOURCE)` and then calls
# pthread_{get,set}affinity_np — glibc-only functions that Bionic does NOT provide.
# Android defines __linux__, so the guard fires and the build fails on undeclared
# identifiers. Exclude Android (__ANDROID__) from these glibc-only guards; ducc0
# falls back to std::thread::hardware_concurrency and a no-op pinning.
ducc_thr="$sp_src/subprojects/duccfft/ducc0/infra/threading.cc"
if [ -f "$ducc_thr" ] && ! grep -q "!defined(__ANDROID__)" "$ducc_thr"; then
    python3 - "$ducc_thr" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "#if __has_include(<pthread.h>) && defined(__linux__) && defined(_GNU_SOURCE)"
new = old + " && !defined(__ANDROID__)"
n = s.count(old)
assert n >= 2, f"expected >=2 ducc0 affinity guards, found {n}"
open(p, "w").write(s.replace(old, new))
print(f"patched {n} ducc0 affinity guards to exclude __ANDROID__")
PY
fi

# Meson cross-file: BLAS/LAPACK names + the pkg-config dir for our OpenBLAS, and
# the long-double format (same x86_64 INTEL_EXTENDED as numpy's cross-file).
cross="$src/scipy-cross-props.ini"
cat > "$cross" <<EOF
[properties]
longdouble_format = 'INTEL_EXTENDED_16_BYTES_LE'

[built-in options]
pkg_config_path = '$openblas_dir/lib/pkgconfig'
EOF

# --- cibuildwheel config -----------------------------------------------------
export CIBW_PLATFORM=android
export CIBW_BUILD="cp${TEMPEST_PYTHON_VERSION:-3.14}-*"
export CIBW_BUILD="${CIBW_BUILD/./}"                 # cp3.14 -> cp314
export CIBW_BUILD_FRONTEND="build"
export CIBW_BEFORE_BUILD=""                          # skip scipy-openblas host hook
export CIBW_TEST_SKIP="*"                            # can't pip-install on the target
# Point meson at OpenBLAS by name (plain libblas/liblapack interface) + the pkg
# config dir, disable Fortran, and turn off Pythran (it would need a host run-check).
export CIBW_CONFIG_SETTINGS="\
setup-args=-D_without-fortran=true \
setup-args=-Dblas=openblas \
setup-args=-Dlapack=openblas \
setup-args=-Duse-pythran=false \
setup-args=--cross-file=$cross \
setup-args=--pkg-config-path=$openblas_dir/lib/pkgconfig"
# Make the staged numpy wheel available so scipy's build-time `import numpy` resolves.
export CIBW_ENVIRONMENT="PKG_CONFIG_PATH=$openblas_dir/lib/pkgconfig PIP_FIND_LINKS=$out"

echo "==> cibuildwheel: scipy $scipy_version (android x86_64, fortran-free + OpenBLAS/C_LAPACK)"
cibuildwheel --platform android --archs x86_64 --output-dir "$out" "$sp_src"

echo
echo "Wheel(s) in $out:"
ls -1 "$out"/scipy-*-android_*_x86_64.whl 2>/dev/null || echo "(no scipy wheel produced)"
