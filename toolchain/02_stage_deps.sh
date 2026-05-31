#!/usr/bin/env bash
# 02_stage_deps.sh — assemble the Android site-packages payload.
#
# Pure-Python deps (pydantic + annotated_types + typing_extensions) come straight
# from PyPI; the compiled pydantic_core comes from the Android wheel built by
# 01_build_wheels.sh. The tempestroid core itself is NOT staged here — the Gradle
# assets task copies it fresh from src/ (minus the Qt renderer) on every build.
#
# Output: toolchain/dist/site-packages/  (consumed by app/build.gradle.kts).
#
# Versions are locked together: pydantic 2.12.5 pins pydantic-core==2.41.5, which
# is exactly the version 01_build_wheels.sh cross-compiles. Bump them in lockstep.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"
WHEELS="$DIST/wheels"
STAGE="$DIST/site-packages"
ABI="arm64-v8a"

PYDANTIC_VERSION="2.12.5"
PYDANTIC_CORE_WHEEL="$WHEELS/pydantic_core-2.41.5-cp314-cp314-android_24_${ABI//-/_}.whl"

echo "==> staging site-packages at $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE"

# 1) Pure-Python deps from PyPI (platform-independent). --no-deps so pip does not
#    drag in a host pydantic_core; we supply the Android one below.
echo "==> downloading pure-Python deps (pydantic==$PYDANTIC_VERSION + friends)"
# uv pip: no bytecode compilation by default, so no host .pyc leaks into the APK.
uv pip install \
    --target "$STAGE" \
    --no-deps \
    "pydantic==$PYDANTIC_VERSION" \
    "annotated-types" \
    "typing-extensions" \
    "typing-inspection" \
    >/dev/null

# 2) The cross-compiled pydantic_core (a wheel is just a zip).
echo "==> unpacking Android pydantic_core wheel"
if [[ ! -f "$PYDANTIC_CORE_WHEEL" ]]; then
    echo "ERROR: missing $PYDANTIC_CORE_WHEEL — run 01_build_wheels.sh first" >&2
    exit 1
fi
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$PYDANTIC_CORE_WHEEL" "$STAGE"

# 3) Drop dist-info + caches we do not need on device (smaller APK).
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$STAGE" -maxdepth 1 -name "*.dist-info" -type d -exec rm -rf {} +

echo "==> staged:"
ls -1 "$STAGE"
echo "==> done. Gradle copyPythonSitePackages will ship this + the tempestroid core."
