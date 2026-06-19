#!/usr/bin/env bash
# 02_stage_deps.sh — assemble the Android site-packages payload.
#
# Pure-Python deps (pydantic + annotated_types + typing_extensions + the extracted
# tempest-core engine) come straight from PyPI; the compiled pydantic_core comes
# from the Android wheel built by 01_build_wheels.sh. The tempestroid core itself
# is NOT staged here — the Gradle assets task copies it fresh from src/ (minus the
# Qt renderer) on every build. tempestroid now imports the renderer-agnostic engine
# from tempest_core, so that pure-Python package MUST be staged here too (else
# `import tempest_core` fails on device).
#
# Output: toolchain/dist/site-packages/  (consumed by app/build.gradle.kts).
#
# Versions are locked together: pydantic 2.12.5 pins pydantic-core==2.41.5, which
# is exactly the version 01_build_wheels.sh cross-compiles. Bump them in lockstep.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"
WHEELS="$DIST/wheels"

# ABI selection (F7): the default arm64-v8a build keeps its UNCHANGED output dir
# (dist/site-packages) so existing arm64 builds are byte-for-byte untouched; an
# x86_64 build (the headless emulator target) stages into a sibling
# dist/site-packages-x86_64 so it never clobbers the arm64 staging. Only the
# compiled pydantic_core wheel differs by ABI (the pure-Python deps are identical).
ABI="${TEMPEST_ABI:-arm64-v8a}"
if [[ "$ABI" == "arm64-v8a" ]]; then
    STAGE="$DIST/site-packages"
else
    STAGE="$DIST/site-packages-$ABI"
fi

PYDANTIC_VERSION="2.12.5"
TEMPEST_CORE_VERSION="0.1.0"
PYDANTIC_CORE_WHEEL="$WHEELS/pydantic_core-2.41.5-cp314-cp314-android_24_${ABI//-/_}.whl"

echo "==> staging site-packages for ABI=$ABI at $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE"

# 1) Pure-Python deps from PyPI (platform-independent). --no-deps so pip does not
#    drag in a host pydantic_core; we supply the Android one below.
echo "==> downloading pure-Python deps (pydantic==$PYDANTIC_VERSION + tempest-core==$TEMPEST_CORE_VERSION + friends)"
# uv pip: no bytecode compilation by default, so no host .pyc leaks into the APK.
uv pip install \
    --target "$STAGE" \
    --no-deps \
    "pydantic==$PYDANTIC_VERSION" \
    "tempest-core==$TEMPEST_CORE_VERSION" \
    "annotated-types" \
    "typing-extensions" \
    "typing-inspection" \
    >/dev/null

# 1b) Vision stack (Trilho G), opt-in via TEMPEST_VISION=1. Stages
#     ort-vision-sdk + pillow + their pure-Python deps WITHOUT onnxruntime:
#     there is no onnxruntime Android wheel, and the SDK lazy-imports it only when
#     no `backend=` is given, so on device inference is bridged to the native
#     onnxruntime-android AAR (the OnnxModule) via AarBackend. numpy must already
#     be staged (it has its own cross-compiled Android wheel; see
#     build_numpy_x86.sh) — it is left in place here.
#
#     We install with --no-deps and an explicit dep list so pip never drags in the
#     host onnxruntime wheel. pillow ships a manylinux wheel by default; on the
#     emulator (x86_64) the host pillow .so happens NOT to be ABI-compatible, but
#     the vision spike that drives the AAR uses numpy-only preprocessing, so the
#     pure-Python ort_vision_sdk + pillow Python sources suffice for the import +
#     the AarBackend path. (A cross-compiled pillow Android wheel is a later step
#     if a model needs PIL-backed decoding on device.)
if [[ "${TEMPEST_VISION:-0}" == "1" ]]; then
    ORT_VISION_VERSION="${ORT_VISION_VERSION:-0.4.0}"
    PILLOW_VERSION="${PILLOW_VERSION:-11.3.0}"
    echo "==> staging vision stack (ort-vision-sdk==$ORT_VISION_VERSION + pillow, no onnxruntime)"
    uv pip install \
        --target "$STAGE" \
        --no-deps \
        "ort-vision-sdk==$ORT_VISION_VERSION" \
        >/dev/null

    # ort-vision-sdk's io/image.py does `from PIL import Image` at import time.
    # The real Pillow ships a compiled `_imaging` C extension with NO Android
    # wheel, and the host (Linux x86_64, cp313) .so files cannot load under the
    # device's CPython 3.14 — importing the SDK would crash. The vision SPIKE only
    # feeds NumPy ndarrays (its `load_image` ndarray branch never touches PIL
    # internals — `Image.Image` is used solely for an isinstance check), so we
    # ship a tiny pure-Python PIL SHIM that satisfies the import + the ndarray
    # path. Decoding a real JPEG/PNG on device needs a cross-compiled Pillow
    # Android wheel (a later G2 step) or the host BitmapFactory bridge.
    echo "==> writing minimal pure-Python PIL shim (ndarray-only image path)"
    rm -rf "$STAGE/PIL" "$STAGE"/pillow.libs "$STAGE"/Pillow*.dist-info
    mkdir -p "$STAGE/PIL"
    cat > "$STAGE/PIL/__init__.py" <<'PIL_INIT'
"""Minimal PIL shim — ndarray-only image path for ort-vision-sdk on device.

The real Pillow has no Android wheel; the vision spike feeds NumPy arrays, so
only ``Image.Image`` (for an isinstance check) and ``UnidentifiedImageError``
need to exist. Both are re-exported at the package top level (``from PIL import
Image, UnidentifiedImageError``) to match real Pillow. Decoding real image files
needs a cross-compiled Pillow wheel.
"""

from PIL import Image as Image
from PIL.Image import UnidentifiedImageError as UnidentifiedImageError

__all__ = ["Image", "UnidentifiedImageError"]
PIL_INIT
    cat > "$STAGE/PIL/Image.py" <<'PIL_IMAGE'
"""Minimal ``PIL.Image`` shim (ndarray-only path, NumPy-backed resize).

The device vision spike feeds NumPy ndarrays. The ort-vision-sdk preprocessing
only touches PIL for ``Image.fromarray(arr).resize((w, h))`` — so this shim wraps
an ndarray and implements ``resize`` with a pure-NumPy bilinear/nearest sampler.
``open`` (file/bytes decoding) is NOT supported — that needs a cross-compiled
Pillow Android wheel (Trilho G2).
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

import numpy as np


class UnidentifiedImageError(OSError):
    """Raised when an image file cannot be identified (shim parity)."""


class Resampling(IntEnum):
    """PIL resampling filters (subset). Bilinear/nearest are implemented."""

    NEAREST = 0
    BILINEAR = 2
    BICUBIC = 3
    LANCZOS = 1


# Module-level aliases real Pillow also exposes.
NEAREST = Resampling.NEAREST
BILINEAR = Resampling.BILINEAR


def _resize_bilinear(arr: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Bilinearly resample an HWC uint8 array to ``(out_h, out_w)``.

    Args:
        arr: Source ``(H, W, C)`` uint8 array.
        out_w: Target width.
        out_h: Target height.

    Returns:
        The resized ``(out_h, out_w, C)`` uint8 array.
    """
    src_h, src_w = arr.shape[:2]
    if src_h == out_h and src_w == out_w:
        return arr.astype(np.uint8, copy=False)
    # Pixel-centre aligned sample coordinates (PIL-like).
    ys = (np.arange(out_h, dtype=np.float64) + 0.5) * (src_h / out_h) - 0.5
    xs = (np.arange(out_w, dtype=np.float64) + 0.5) * (src_w / out_w) - 0.5
    ys = np.clip(ys, 0, src_h - 1)
    xs = np.clip(xs, 0, src_w - 1)
    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    y1 = np.minimum(y0 + 1, src_h - 1)
    x1 = np.minimum(x0 + 1, src_w - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]
    src = arr.astype(np.float64)
    ia = src[np.ix_(y0, x0)]
    ib = src[np.ix_(y0, x1)]
    ic = src[np.ix_(y1, x0)]
    idd = src[np.ix_(y1, x1)]
    top = ia * (1 - wx) + ib * wx
    bot = ic * (1 - wx) + idd * wx
    out = top * (1 - wy) + bot * wy
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


class Image:
    """Thin ndarray wrapper supporting the SDK's resize/convert/asarray path."""

    def __init__(self, array: np.ndarray) -> None:
        """Wrap an HWC uint8 RGB array.

        Args:
            array: The source ``(H, W, C)`` uint8 array.
        """
        self._array = np.ascontiguousarray(array)

    def convert(self, mode: str) -> "Image":
        """Return self (the spike feeds RGB arrays; mode conversion is a no-op).

        Args:
            mode: The target mode (ignored).

        Returns:
            This image.
        """
        return self

    def resize(self, size: tuple[int, int], resample: Any = None) -> "Image":
        """Resize to ``(width, height)`` using a NumPy sampler.

        Args:
            size: Target ``(width, height)`` in pixels.
            resample: The resampling filter (bilinear by default).

        Returns:
            A new resized :class:`Image`.
        """
        out_w, out_h = int(size[0]), int(size[1])
        if resample == Resampling.NEAREST:
            src_h, src_w = self._array.shape[:2]
            yi = np.clip((np.arange(out_h) * src_h // out_h), 0, src_h - 1)
            xi = np.clip((np.arange(out_w) * src_w // out_w), 0, src_w - 1)
            return Image(self._array[np.ix_(yi, xi)])
        return Image(_resize_bilinear(self._array, out_w, out_h))

    def __array__(self, dtype: Any = None) -> np.ndarray:
        """Expose the underlying array to ``np.asarray``.

        Args:
            dtype: Optional dtype for the returned array.

        Returns:
            The wrapped array (cast to ``dtype`` if given).
        """
        if dtype is not None:
            return self._array.astype(dtype)
        return self._array

    def __enter__(self) -> "Image":
        """Context-manager entry (``with Image.open(...) as img``)."""
        return self

    def __exit__(self, *exc: Any) -> None:
        """Context-manager exit (no resources to release)."""
        return None


def fromarray(obj: np.ndarray, mode: Any = None) -> Image:
    """Wrap an ndarray as a shim :class:`Image` (matches ``PIL.Image.fromarray``).

    Args:
        obj: The source ``(H, W, C)`` uint8 array.
        mode: Unused.

    Returns:
        A shim :class:`Image` wrapping ``obj``.
    """
    return Image(np.asarray(obj))


def open(fp: Any, mode: str = "r", formats: Any = None) -> Image:  # noqa: A001
    """Refuse to decode — the device path uses NumPy ndarrays only.

    Args:
        fp: The file/bytes source (unsupported by the shim).
        mode: Unused.
        formats: Unused.

    Raises:
        UnidentifiedImageError: Always — file/bytes decoding needs a real Pillow.
    """
    raise UnidentifiedImageError(
        "PIL shim cannot decode image files on device; feed a NumPy ndarray "
        "(a cross-compiled Pillow Android wheel is needed for file decoding)."
    )
PIL_IMAGE
    echo "==> PIL shim staged (real Pillow $PILLOW_VERSION not shipped — no Android wheel)"
fi

# 2) The cross-compiled pydantic_core (a wheel is just a zip).
echo "==> unpacking Android pydantic_core wheel"
if [[ ! -f "$PYDANTIC_CORE_WHEEL" ]]; then
    echo "ERROR: missing $PYDANTIC_CORE_WHEEL — run 01_build_wheels.sh first" >&2
    exit 1
fi
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$PYDANTIC_CORE_WHEEL" "$STAGE"

# 2b) The cross-compiled numpy Android wheel (non-arm64 ABIs only — there is no
#     arm64 numpy wheel yet, see build_numpy_x86.sh). Because step 0 wipes $STAGE,
#     re-staging numpy here keeps the x86_64 site-packages reproducible (the spike
#     + the vision stack import numpy). Skipped silently when the wheel is absent.
if [[ "$ABI" != "arm64-v8a" ]]; then
    NUMPY_WHEEL="$(ls "$DIST/wheels-$ABI"/numpy-*-android_*_"${ABI//-/_}".whl 2>/dev/null | head -1 || true)"
    if [[ -n "$NUMPY_WHEEL" && -f "$NUMPY_WHEEL" ]]; then
        echo "==> unpacking Android numpy wheel ($(basename "$NUMPY_WHEEL"))"
        python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
            "$NUMPY_WHEEL" "$STAGE"
    else
        echo "==> WARN: no numpy Android wheel under $DIST/wheels-$ABI — run build_numpy_x86.sh" >&2
    fi
fi

# 3) Drop dist-info + caches we do not need on device (smaller APK).
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$STAGE" -maxdepth 1 -name "*.dist-info" -type d -exec rm -rf {} +

echo "==> staged:"
ls -1 "$STAGE"
echo "==> done. Gradle copyPythonSitePackages will ship this + the tempestroid core."
