"""UI test for the ONNX vision spike — proves the AAR inference path on device.

Run headless (uses the in-process ``onnxruntime`` wheel on the desktop) with::

    uv run tempest uitest examples/visionspike/test_visionspike.py

and on the emulator (the real proof — the native ``onnxruntime-android`` AAR via
:class:`~tempestroid.native.inference.AarBackend`) with::

    uv run tempest uitest examples/visionspike/test_visionspike.py --target emulator

The app decodes a real test photo (``banana.jpg``) — on device via the host's
``BitmapFactory`` (no Pillow/OpenCV wheel) — loads ``squeezenet1.1.onnx``,
classifies it, and renders "inference OK" (green) plus the predicted ImageNet
class + provider + latency, or "inference FAILED" (red) with the traceback. A
passing test means a real ``ort-vision-sdk`` ``Classifier`` ran on the target
through the bridge and predicted the bundled object (``banana``).
"""

from __future__ import annotations

from app import make_state, view  # noqa: F401 — the app contract the driver loads

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_classifier_runs_through_aar(page: Page) -> None:
    """A real Classifier decodes + classifies the bundled photo on the target."""
    await page.expect_text("inference OK")
    # The bundled banana.jpg: squeezenet1.1's stable top-1 is "banana".
    await page.expect_text("banana")
