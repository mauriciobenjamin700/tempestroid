#!/usr/bin/env bash
# G6 — cross-compile OpenBLAS (BLAS + f2c-translated LAPACK) for Android x86_64.
#
# scipy/sklearn need BLAS *and* LAPACK (unlike numpy, which builds noblas). The
# Android NDK ships clang ONLY — no Fortran compiler of any kind (gfortran/flang)
# — which is the documented "calcanhar" of Trilho G (docs/research/onnx-ml-stack.md
# §2). OpenBLAS sidesteps this: with `NOFORTRAN=1` it compiles a copy of LAPACK
# that was machine-translated to C with `f2c` (the "C_LAPACK" path), so we get a
# full BLAS + LAPACK with the NDK clang and zero Fortran.
#
# This is the foundation dependency for the scipy attempt (build_scipy_x86.sh):
# scipy with `-D_without-fortran=true` links against this OpenBLAS via pkg-config.
#
# Output: toolchain/dist/openblas-x86_64/ (libopenblas.a + headers + .pc)
#
# Prereqs: Android SDK/NDK r27 (ANDROID_SDK_ROOT=/usr/lib/android-sdk on this host),
# host gcc + make. Does NOT run in WSL without the NDK toolchain.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$here/.src"
out="$here/dist/openblas-x86_64"
openblas_version="${OPENBLAS_VERSION:-0.3.33}"
ndk="${ANDROID_NDK_ROOT:-/usr/lib/android-sdk/ndk/27.3.13750724}"
api="${ANDROID_API:-24}"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_NDK_ROOT="$ndk"

# --- preflight ---------------------------------------------------------------
[ -d "$ndk" ] || { echo "NDK not found: $ndk" >&2; exit 1; }
command -v make >/dev/null || { echo "need host make" >&2; exit 1; }
command -v gcc  >/dev/null || { echo "need host gcc (HOSTCC)" >&2; exit 1; }
mkdir -p "$src" "$out"

tc="$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"
cc="$tc/x86_64-linux-android${api}-clang"
ar="$tc/llvm-ar"
ranlib="$tc/llvm-ranlib"
[ -x "$cc" ] || { echo "android clang not found: $cc" >&2; exit 1; }

# --- OpenBLAS source ---------------------------------------------------------
ob_src="$src/OpenBLAS-$openblas_version"
if [ ! -d "$ob_src" ]; then
    echo "==> fetching OpenBLAS $openblas_version"
    url="https://github.com/OpenMathLib/OpenBLAS/releases/download/v${openblas_version}/OpenBLAS-${openblas_version}.tar.gz"
    curl -sL "$url" -o "$src/OpenBLAS-$openblas_version.tar.gz"
    tar xzf "$src/OpenBLAS-$openblas_version.tar.gz" -C "$src"
fi

# --- build -------------------------------------------------------------------
# NOFORTRAN=1  -> no Fortran compiler; OpenBLAS builds the f2c-translated LAPACK.
# C_LAPACK=1   -> explicitly select the C (f2c) LAPACK sources.
# TARGET=ATOM  -> generic SSE2/SSE3 x86_64 baseline that runs on the emulator.
# BINARY=64    -> 64-bit.
# HOSTCC=gcc   -> host tools (getarch etc.) build with the native compiler.
# NO_SHARED=1  -> static .a only (we link it statically into the scipy wheel).
# USE_OPENMP=0 -> avoid pulling libomp into BLAS; sklearn handles OpenMP itself.
echo "==> building OpenBLAS for android x86_64 (NOFORTRAN + C_LAPACK)"
make -C "$ob_src" -j"$(nproc)" \
    HOSTCC=gcc \
    CC="$cc" \
    AR="$ar" \
    RANLIB="$ranlib" \
    TARGET=ATOM \
    BINARY=64 \
    NOFORTRAN=1 \
    C_LAPACK=1 \
    NO_SHARED=1 \
    USE_OPENMP=0 \
    NUM_THREADS=8

echo "==> installing to $out"
make -C "$ob_src" \
    PREFIX="$out" \
    NO_SHARED=1 \
    install

echo
echo "OpenBLAS staged in $out:"
ls -1 "$out/lib" 2>/dev/null || true
echo "pkg-config files:"
find "$out" -name "*.pc" 2>/dev/null || true
