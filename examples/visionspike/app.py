"""G1 spike — run a real ONNX classifier on the device through the AAR backend.

The Trilho G milestone: an ``ort-vision-sdk`` :class:`~ort_vision_sdk.Classifier`
classifies an image **on the device**, with preprocessing/postprocessing in NumPy
(Python) and the model inference bridged to the native ``onnxruntime-android`` AAR
via :class:`~tempestroid.native.inference.AarBackend`. There is no ``onnxruntime``
Python wheel for Android — the inference runs in Kotlin/C++ on the host.

The screen shows a green "inference OK" line with the predicted ImageNet class +
the execution provider the host used + the inference latency, or a red
"inference FAILED" line with the traceback if anything along the path breaks — so
the screenshot is self-describing either way.

The model (``squeezenet1.1.onnx``, ImageNet, input ``1x3x224x224``), the
``imagenet_labels.txt`` labels, and a real test photo (``banana.jpg``) ride along
in the app bundle (``tempest`` ships the whole project tree to the device), so the
app finds them next to ``__file__``. The photo is decoded **on device** via the
host's ``BitmapFactory`` (``tempestroid.native.image.decode_image``) — no Pillow
or OpenCV wheel in the APK — into a NumPy array fed straight to the SDK.

**G4 model delivery.** By default the model is the **embedded** bundled asset
(extracted with the app bundle). Set ``VISIONSPIKE_MODEL_URL`` to switch to the
**download** strategy: :func:`tempestroid.native.ensure_model` fetches the model
(off the loop, stdlib ``urllib``) into a writable on-device cache
(``tempfile.gettempdir()/tempest_models`` → the app's ``cacheDir`` on Android),
verifies an optional ``VISIONSPIKE_MODEL_SHA256``, and caches it so a second
launch skips the network. The detail line reports ``source=download`` vs
``source=embedded`` so the screenshot is self-describing.

This is intentionally renderer-agnostic (no top-level Qt import): it runs in the
Qt simulator (with the in-process ``onnxruntime`` wheel) AND on the
emulator/device (with the AAR bridge), the import of which is decided at runtime.

Runs in the Qt simulator (needs ``onnxruntime`` + ``ort-vision-sdk`` installed)::

    uv run python examples/visionspike/app.py
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from tempestroid import (
    App,
    Color,
    Column,
    Edge,
    FontWeight,
    Style,
    Text,
    Widget,
)
from tempestroid.native import ensure_model
from tempestroid.native.dispatch import on_device

_HERE = Path(__file__).resolve().parent
#: The fp32 baseline model (G1/G2 device-verify; ~4.8 MiB).
_MODEL_FP32 = _HERE / "squeezenet1.1.onnx"
#: The INT8-quantized ``.ort`` (G3; ~1.3 MiB, 72% smaller) — onnxruntime loads
#: ``.ort`` the same as ``.onnx`` through the AAR.
_MODEL_INT8_ORT = _HERE / "squeezenet1.1.int8.ort"
#: Which model to load. Set ``VISIONSPIKE_MODEL=fp32`` to use the baseline
#: ``.onnx``; the default is the G3 quantized ``.ort`` artifact (when present).
_USE_INT8 = os.environ.get("VISIONSPIKE_MODEL", "int8").lower() != "fp32"
_MODEL = (
    _MODEL_INT8_ORT if (_USE_INT8 and _MODEL_INT8_ORT.exists()) else _MODEL_FP32
)
_LABELS = _HERE / "imagenet_labels.txt"
#: G4 download+cache demo: when set, the model is *fetched at runtime* from this
#: URL into an on-device cache (instead of resolving the bundled asset above),
#: proving the download delivery strategy end to end. Unset = embedded default.
_MODEL_URL = os.environ.get("VISIONSPIKE_MODEL_URL", "").strip()
#: Optional expected SHA-256 of the downloaded model (verifies the cached file).
_MODEL_SHA256 = os.environ.get("VISIONSPIKE_MODEL_SHA256", "").strip() or None
#: Writable on-device cache dir for downloaded models. ``tempfile.gettempdir()``
#: resolves to the app's ``cacheDir`` on Android (the host sets ``TMPDIR`` to it
#: in ``MainActivity``), and to the OS temp dir on the desktop — both writable
#: without a permission grant. ONNX Runtime mmaps the file on load, so caching it
#: here does not pull the whole model into RAM.
_MODEL_CACHE_DIR = Path(tempfile.gettempdir()) / "tempest_models"
#: A real ImageNet object photo (squeezenet1.1 top-1 is a stable "banana").
_IMAGE = _HERE / "banana.jpg"
#: SqueezeNet 1.1 takes 224x224 RGB (ImageNet-normalised inside the SDK).
_INPUT_SIZE = (224, 224)
#: Cap the longest side on decode (BitmapFactory subsamples a large photo).
_DECODE_MAX_SIZE = 640

_BG = Color.from_hex("#0b0f14")
_OK = Color.from_hex("#22c55e")
_ERR = Color.from_hex("#ef4444")
_TEXT = Color.from_hex("#f9fafb")
_SUBTLE = Color.from_hex("#9ca3af")


@dataclass
class SpikeState:
    """Inference result state, filled by the async classification.

    Attributes:
        done: Whether the inference has completed (success or failure).
        ok: Whether the inference succeeded.
        title_line: The headline status (predicted class, or the error class).
        detail_line: The supporting detail (provider + latency, or traceback).
    """

    done: bool = False
    ok: bool = False
    title_line: str = "running inference..."
    detail_line: str = field(default="loading model + classifying a test image")


def make_state() -> SpikeState:
    """Build a fresh state.

    Returns:
        A new spike state (pre-inference).
    """
    return SpikeState()


async def _load_test_image() -> object:
    """Decode the bundled test photo to a HWC uint8 RGB NumPy array.

    On device the decode is bridged to the host's ``BitmapFactory`` via
    :func:`tempestroid.native.image.decode_image` (no Pillow/OpenCV wheel in the
    APK); in the Qt simulator the same file is decoded with the desktop ``Pillow``
    (present in the dev environment). Both yield the identical ``(H, W, 3)``
    ``uint8`` RGB array the SDK's ``predict`` accepts directly.

    Returns:
        An ``(H, W, 3)`` ``uint8`` NumPy array of the test photo.
    """
    if on_device():
        from tempestroid.native.image import decode_image

        return await decode_image(_IMAGE, max_size=_DECODE_MAX_SIZE)

    # Desktop path: decode with Pillow (no host bridge in the simulator).
    import numpy as np
    from PIL import Image

    return np.array(Image.open(_IMAGE).convert("RGB"))


async def _classify(app: App[SpikeState]) -> None:
    """Load the model and classify one test image, recording the result.

    On device this drives the native ``onnxruntime-android`` AAR through
    :class:`AarBackend`; in the Qt simulator it falls back to the in-process
    ``onnxruntime`` wheel (no backend), so the same app exercises both leaves.

    Args:
        app: The running app, whose state is updated with the outcome.
    """
    try:
        from ort_vision_sdk import Classifier

        labels = str(_LABELS) if _LABELS.exists() else None
        start = time.perf_counter()
        provider = "in-process ORT"

        # G4 delivery strategy: download+cache when a URL is given, else the
        # embedded bundled asset. ``ensure_model`` is cache-first (a second launch
        # returns the cached file without a network call) and runs off the loop.
        if _MODEL_URL:
            model_path = await ensure_model(
                _MODEL_URL, _MODEL_CACHE_DIR, sha256=_MODEL_SHA256
            )
            source = "download"
        else:
            model_path = _MODEL
            source = "embedded"

        if on_device():
            # Device path: bridge inference to the native AAR.
            from tempestroid.native.inference import AarBackend

            backend = await AarBackend.create(model_path)
            provider = "AAR"
            clf = Classifier(
                str(model_path),
                backend=backend,
                labels=labels,
                input_size=_INPUT_SIZE,
            )
        else:
            # Desktop path: the in-process onnxruntime wheel.
            clf = Classifier(
                str(model_path), labels=labels, input_size=_INPUT_SIZE
            )

        image = await _load_test_image()
        results = await clf.ort_async_predict(image)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result = results[0]
        top1_name = result.name
        top1_conf = float(result.probs.top1conf)

        app.state.done = True
        app.state.ok = True
        app.state.title_line = f"top-1: {top1_name}  ({top1_conf * 100:.1f}%)"
        app.state.detail_line = (
            f"source={source}  model={model_path.name}  provider={provider}  "
            f"latency={elapsed_ms:.0f} ms"
        )
        # Machine-readable marker on stdout → device logcat. Lets a headless
        # harness (emulator_verify.sh EMU_EXPECT) assert that REAL inference ran
        # end-to-end (decode → numpy pre/post → onnxruntime AAR) on the emulator,
        # not just that the app mounted. Kept a single stable line.
        print(
            f"VISIONSPIKE_RESULT ok=1 top1={top1_name} "
            f"conf={top1_conf:.4f} provider={provider} latency_ms={elapsed_ms:.0f}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 — surface ANY failure on screen
        app.state.done = True
        app.state.ok = False
        app.state.title_line = f"{type(exc).__name__}"
        app.state.detail_line = str(exc)[:240]
        print(f"VISIONSPIKE_RESULT ok=0 error={type(exc).__name__}", flush=True)
    app.request_rebuild()


def view(app: App[SpikeState]) -> Widget:
    """Build the spike screen, kicking off classification on first build.

    Args:
        app: The running app.

    Returns:
        The root widget showing the classification status.
    """
    state = app.state
    # Kick off the async classification once, on the first build. The app runs on
    # an asyncio loop (qasync in the sim, the device loop on Android), so schedule
    # the coroutine as a loop task; guard against re-scheduling with the title.
    if not state.done and state.title_line == "running inference...":
        state.title_line = "classifying..."
        asyncio.ensure_future(_classify(app))

    if not state.done:
        status_text = "running..."
        status_color = _SUBTLE
    elif state.ok:
        status_text = "inference OK"
        status_color = _OK
    else:
        status_text = "inference FAILED"
        status_color = _ERR

    return Column(
        style=Style(
            background=_BG,
            padding=Edge.all(24),
            gap=14,
            grow=1,
        ),
        children=[
            Text(
                content="Trilho G — ONNX on device (AAR)",
                style=Style(color=_TEXT, font_size=22, font_weight=FontWeight.BOLD),
                key="title",
            ),
            Text(
                content=status_text,
                style=Style(
                    color=status_color,
                    font_size=18,
                    font_weight=FontWeight.BOLD,
                ),
                key="status",
            ),
            Text(
                content=state.title_line,
                style=Style(color=_TEXT, font_size=15),
                key="result",
            ),
            Text(
                content=state.detail_line,
                style=Style(color=_SUBTLE, font_size=13),
                key="detail",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — ONNX spike", size=(460, 280))
    )
