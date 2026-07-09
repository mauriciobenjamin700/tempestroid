"""Renderer-aware on-device computer vision: ONNX inference + image codec.

A vision app runs the same ONNX graphs and image (de)coding on two very different
targets and should never branch on which one it is:

* **Android device** — there is no cross-compiled ``onnxruntime`` or Pillow wheel,
  so graphs run through the native ``onnxruntime-android`` AAR
  (:class:`tempestroid.native.inference.AarBackend`) and images are decoded by the
  host's ``BitmapFactory`` (:func:`tempestroid.native.image.decode_image`). Python
  still owns the NumPy pre/post-processing.
* **Desktop / Qt simulator** — the in-process ``onnxruntime`` wheel and Pillow.

This module hides that split behind three primitives so the app only expresses its
*domain* pipeline (which models, thresholds, crop/label logic):

* :class:`OrtSession` — load + run an ONNX model, same ``run`` / ``input_name`` /
  ``output_names`` surface on both backends.
* :func:`decode_image` — encoded bytes/path → HWC ``uint8`` RGB array.
* :func:`encode_image` — HWC ``uint8`` RGB array → ``(base64, mime)``: a
  pure-NumPy PNG on device (the Pillow shim cannot encode), JPEG on the desktop.

``numpy`` is imported lazily inside the functions/methods that need it, so
importing this module (or ``tempestroid``) never pulls NumPy into a lean install
that ships no vision feature.

Example (identical on device and desktop)::

    from tempestroid.vision import OrtSession, decode_image, encode_image

    session = await OrtSession.create("detector.onnx")
    image = await decode_image(image_bytes)                    # HWC uint8 RGB
    outputs = await session.run({session.input_name: tensor})  # list[np.ndarray]
    b64, mime = encode_image(crop)                             # for a data: URI
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import os
import struct
import zlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from tempestroid.native.dispatch import on_device
from tempestroid.native.image import decode_image as _native_decode_image

if TYPE_CHECKING:
    import numpy as np

__all__ = ["OrtSession", "decode_image", "encode_image"]


@contextlib.contextmanager
def _suppress_fd(fileno: int) -> Iterator[None]:
    """Silence a C-level file descriptor for the duration of the block.

    ``onnxruntime``'s native layer writes a GPU device-discovery warning straight
    to ``stderr`` (fd 2), bypassing Python logging, the first time it is imported.
    Redirecting the fd to ``os.devnull`` around the import keeps the dev terminal
    clean; Python-level exceptions are unaffected (only the raw text is dropped).

    Args:
        fileno: The file descriptor to silence (e.g. ``2`` for stderr).

    Yields:
        None — control runs the wrapped block with the fd redirected.
    """
    saved = os.dup(fileno)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, fileno)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(saved, fileno)
        os.close(saved)


class OrtSession:
    """An ONNX session backed by the AAR (device) or ``onnxruntime`` (desktop).

    Construct with :meth:`create`. Exactly one of the two backends is set; the
    public surface (:meth:`run` / :attr:`input_name` / :attr:`output_names`) hides
    which, so an app's pipeline is identical on both targets.

    Attributes:
        _ort: The desktop ``onnxruntime.InferenceSession`` (``None`` on device).
        _aar: The device ``AarBackend`` (``None`` on the desktop).
    """

    def __init__(
        self,
        *,
        ort_session: Any = None,  # noqa: ANN401 — onnxruntime.InferenceSession (no wheel on device to type against)
        aar: Any = None,  # noqa: ANN401 — AarBackend (imported lazily to keep NumPy out of lean installs)
    ) -> None:
        """Wrap exactly one backend.

        Args:
            ort_session: A built ``onnxruntime.InferenceSession`` (desktop), or
                ``None`` on device.
            aar: A loaded ``AarBackend`` (device), or ``None`` on the desktop.
        """
        self._ort: Any = ort_session
        self._aar: Any = aar

    @classmethod
    async def create(
        cls, model_path: str, *, providers: list[str] | None = None
    ) -> OrtSession:
        """Load a model into a session, picking the backend for the platform.

        On device the model runs through the native ``onnxruntime-android`` AAR
        (there is no ``onnxruntime`` wheel for Android); on the desktop / Qt
        simulator the in-process ``onnxruntime`` wheel builds a real
        :class:`onnxruntime.InferenceSession`.

        Args:
            model_path: Absolute path to the ``.onnx`` model file.
            providers: Optional execution-provider hint. On device it is forwarded
                to the host (which pins the CPU EP when it contains ``"cpu"`` — a
                fp16 or dynamic-shape graph that NNAPI mis-runs then runs
                correctly). On the desktop it is passed straight to
                ``onnxruntime`` (defaults to ``["CPUExecutionProvider"]``).

        Returns:
            A ready :class:`OrtSession` (AAR-backed on device, ``onnxruntime`` on
            the desktop).
        """
        hint = providers if providers is not None else ["CPUExecutionProvider"]
        if on_device():
            # No onnxruntime wheel on Android — bridge to the native AAR. The
            # factory loads the model on the host and captures its I/O metadata.
            from tempestroid.native.inference import AarBackend

            backend = await AarBackend.create(model_path, providers=hint)
            return cls(aar=backend)

        # Desktop / Qt simulator: the in-process onnxruntime wheel. Import lazily
        # (it does not exist on device) and quiet its startup chatter.
        with _suppress_fd(2):
            import onnxruntime as ort

            ort.set_default_logger_severity(3)

        options = ort.SessionOptions()
        options.log_severity_level = 3

        def _build() -> Any:  # noqa: ANN401 — onnxruntime.InferenceSession (untyped on device)
            return ort.InferenceSession(
                model_path, sess_options=options, providers=hint
            )

        session = await asyncio.to_thread(_build)
        return cls(ort_session=session)

    @property
    def input_name(self) -> str:
        """The model's first input name."""
        if self._aar is not None:
            return str(self._aar.input_name)
        return str(self._ort.get_inputs()[0].name)

    @property
    def output_names(self) -> list[str]:
        """The model's output names, in declared order."""
        if self._aar is not None:
            return [str(n) for n in self._aar.output_names]
        return [str(output.name) for output in self._ort.get_outputs()]

    async def run(self, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        """Run inference and return outputs in :attr:`output_names` order.

        The blocking ``run`` is offloaded to a worker thread so the app's event
        loop is never stalled.

        Args:
            feeds: Mapping of input name to its NumPy array.

        Returns:
            The model outputs as NumPy arrays, in ``output_names`` order.
        """
        if self._aar is not None:
            # AarBackend.run is sync + worker-thread only (it schedules the bridge
            # round-trip on the app loop); to_thread satisfies both.
            return await asyncio.to_thread(self._aar.run, feeds)
        return await asyncio.to_thread(self._ort.run, None, feeds)


async def decode_image(
    source: bytes | str, *, max_size: int | None = None
) -> np.ndarray:
    """Decode encoded image bytes/path into an HWC ``uint8`` RGB array.

    On device there is no cross-compiled Pillow wheel (the bundled ``PIL`` is a
    NumPy-only shim that refuses to decode files), so decoding is bridged to the
    host's ``BitmapFactory`` via :func:`tempestroid.native.image.decode_image`. On
    the desktop the real Pillow decodes in-process.

    Args:
        source: Encoded image bytes (JPEG/PNG/…) or a filesystem path.
        max_size: Optional cap on the longest side (device decode only); ``None``
            decodes at full resolution.

    Returns:
        The decoded ``(H, W, 3)`` ``uint8`` RGB array.
    """
    if on_device():
        return await _native_decode_image(source, max_size=max_size)

    import numpy as np
    from PIL import Image

    if isinstance(source, (str, os.PathLike)):
        with Image.open(source) as img:
            return np.asarray(img.convert("RGB"))
    with Image.open(io.BytesIO(bytes(source))) as img:
        return np.asarray(img.convert("RGB"))


def _png_bytes(arr: np.ndarray) -> bytes:
    """Encode an HWC ``uint8`` RGB array as PNG bytes (pure NumPy + zlib).

    Used on device, where the Pillow shim cannot encode. Writes a minimal
    truecolor (8-bit RGB) PNG: signature, ``IHDR``, one zlib-compressed ``IDAT``
    (each scanline prefixed with filter byte 0), and ``IEND``.

    Args:
        arr: HWC ``uint8`` RGB array.

    Returns:
        The PNG file bytes.
    """
    import numpy as np

    rgb = np.ascontiguousarray(arr[:, :, :3].astype(np.uint8))
    height, width = rgb.shape[:2]
    # Prefix every scanline with a 0 (None) filter byte, then zlib-compress.
    raw = np.hstack(
        [np.zeros((height, 1), dtype=np.uint8), rgb.reshape(height, width * 3)]
    ).tobytes()
    compressed = zlib.compress(raw, 6)

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


def encode_image(arr: np.ndarray, *, quality: int = 92) -> tuple[str, str]:
    """Encode an HWC ``uint8`` RGB array as base64, returning ``(data, mime)``.

    On device the Pillow shim has no encoder, so a pure-NumPy/zlib PNG is emitted
    (``image/png``). On the desktop Pillow writes a JPEG (``image/jpeg``). The
    returned data carries no ``data:`` URI prefix — the caller builds
    ``f"data:{mime};base64,{data}"`` for an :class:`~tempestroid.widgets.Image`.

    Args:
        arr: HWC ``uint8`` RGB array.
        quality: JPEG quality (0–100), desktop only.

    Returns:
        ``(base64_string, mime_type)``.
    """
    if on_device():
        return base64.b64encode(_png_bytes(arr)).decode("ascii"), "image/png"

    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(arr).save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/jpeg"
