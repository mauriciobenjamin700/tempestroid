"""Decode image files to NumPy arrays on the device (Trilho G2).

ONNX vision needs an image decoded to a tensor, but there is no cross-compiled
Pillow wheel for Android (libjpeg/zlib native deps), so file/byte decoding can't
run in Python on device. Instead we bridge decoding to the host's
``BitmapFactory`` (Kotlin ``image`` native module): it decodes JPEG/PNG/WebP/…
natively, downsamples to an optional size cap, and returns the raw RGB pixels,
which this module reassembles into a canonical **HWC uint8 RGB** ``ndarray`` —
exactly the array the ``ort-vision-sdk`` accepts as ``predict`` input.

So the vision pipeline on device is: ``decode_image`` (native BitmapFactory) →
``ndarray`` → SDK preprocessing/inference (NumPy pre/post + the AAR backend, see
:mod:`tempestroid.native.inference`). No ``opencv-python`` and no Pillow wheel in
the APK; only the NumPy-backed resize shim plus this native decode.

Usage on device::

    from tempestroid.native.image import decode_image
    from tempestroid.native.inference import AarBackend
    from ort_vision_sdk import Classifier

    image = await decode_image("photo.jpg", max_size=640)   # HWC uint8 RGB
    clf = Classifier("model.onnx", backend=await AarBackend.create("model.onnx"))
    results = await clf.ort_async_predict(image)
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

from tempestroid.native.dispatch import NativeError, send_native_request

if TYPE_CHECKING:
    import numpy as np

__all__ = ["decode_image"]

#: Native module name routed by the host's ``NativeModules`` to the image module.
_MODULE = "image"


async def decode_image(
    source: str | Path | bytes,
    *,
    max_size: int | None = None,
) -> np.ndarray:
    """Decode an image to a HWC uint8 RGB array via the host's ``BitmapFactory``.

    Bridges decoding to the native ``image`` module: a filesystem path (``str``/
    :class:`~pathlib.Path`) is decoded by path; raw ``bytes`` (an encoded JPEG/
    PNG/… buffer) are base64-sent and decoded from memory. The host optionally
    downsamples so the longest side is at most ``max_size`` (caps decode memory
    for large photos), then returns the raw RGB pixels.

    Args:
        source: An image file path, or the encoded image bytes.
        max_size: Optional cap on the longest side (pixels); ``None`` decodes at
            full resolution. The host uses power-of-two subsampling, so the
            result may be larger than ``max_size`` but never smaller.

    Returns:
        A ``numpy.ndarray`` of shape ``(H, W, 3)``, dtype ``uint8``, RGB — the
        canonical input the ``ort-vision-sdk`` tasks accept directly.

    Raises:
        NativeError: If the host cannot decode the source (``decode_failed``),
            or the file is missing (``not_found``).
        ValueError: If the host's reply is malformed.
    """
    import numpy as np

    args: dict[str, object] = {}
    if isinstance(source, (str, Path)):
        args["path"] = str(source)
    else:
        args["bytes"] = base64.b64encode(bytes(source)).decode("ascii")
    if max_size is not None:
        args["max_size"] = int(max_size)

    data = await send_native_request(_MODULE, "decode", args)
    width = int(data.get("width", 0))
    height = int(data.get("height", 0))
    encoded = data.get("data")
    if width <= 0 or height <= 0 or not isinstance(encoded, str):
        raise ValueError(f"image decode returned a malformed reply: {data!r}")

    raw = base64.b64decode(encoded)
    expected = width * height * 3
    if len(raw) != expected:
        raise NativeError(
            "decode_failed",
            f"expected {expected} RGB bytes ({width}x{height}x3), got {len(raw)}",
        )
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
