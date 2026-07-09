"""Unit tests for :mod:`tempestroid.vision` — the renderer-aware CV primitives.

Covers the desktop path directly and the device path by monkeypatching
``on_device`` (the codec's only platform branch), plus a round-trip of the ONNX
session against a tiny in-memory model.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np
import pytest

from tempestroid import vision


def _sample_rgb() -> np.ndarray:
    """A small deterministic HWC uint8 RGB array."""
    arr = np.zeros((4, 6, 3), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:2, :, 1] = 100
    arr[:, 3:, 2] = 255
    return arr


def test_encode_image_desktop_is_jpeg() -> None:
    """On the desktop ``encode_image`` returns a JPEG data payload + mime."""
    data, mime = vision.encode_image(_sample_rgb())
    assert mime == "image/jpeg"
    raw = base64.b64decode(data)
    assert raw[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_encode_image_device_is_lossless_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """On device ``encode_image`` emits a pure-NumPy PNG (the Pillow shim can't
    encode) that is lossless — Pillow reads back the same pixels."""
    pil = pytest.importorskip("PIL.Image")
    monkeypatch.setattr(vision, "on_device", lambda: True)
    arr = _sample_rgb()
    data, mime = vision.encode_image(arr)
    assert mime == "image/png"
    raw = base64.b64decode(data)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature
    with pil.open(io.BytesIO(raw)) as img:
        decoded = np.asarray(img.convert("RGB"))
    assert decoded.shape == arr.shape
    assert np.array_equal(decoded, arr)


@pytest.mark.asyncio
async def test_decode_image_desktop_roundtrip() -> None:
    """Desktop ``decode_image`` decodes encoded bytes to the canonical HWC RGB array."""
    pil = pytest.importorskip("PIL.Image")
    arr = _sample_rgb()
    buf = io.BytesIO()
    pil.fromarray(arr).save(buf, format="PNG")
    decoded = await vision.decode_image(buf.getvalue())
    assert decoded.dtype == np.uint8
    assert decoded.shape == arr.shape
    assert np.array_equal(decoded, arr)


@pytest.mark.asyncio
async def test_ort_session_desktop_runs_a_model(tmp_path: Path) -> None:
    """``OrtSession`` builds an onnxruntime session on desktop and runs it."""
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    node = helper.make_node("Identity", ["x"], ["y"])
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 3])
    graph = helper.make_graph([node], "id", [x], [y])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    path = tmp_path / "identity.onnx"
    onnx.save(model, str(path))

    session = await vision.OrtSession.create(str(path))
    assert session.input_name == "x"
    assert session.output_names == ["y"]
    feed = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    (out,) = await session.run({"x": feed})
    assert np.array_equal(out, feed)


def test_crop_box_clamps_and_falls_back() -> None:
    """``crop_box`` intersects with the image and falls back on a degenerate box."""
    img = np.arange(10 * 8 * 3, dtype=np.uint8).reshape(10, 8, 3)
    # In-bounds crop.
    crop = vision.crop_box(img, 2, 3, 4, 5)
    assert crop.shape == (5, 4, 3)
    assert np.array_equal(crop, img[3:8, 2:6])
    # Spills past the right/bottom edge → clamped to the image extent.
    clamped = vision.crop_box(img, 6, 7, 100, 100)
    assert clamped.shape == (3, 2, 3)
    # Entirely off-image (degenerate) → whole image.
    assert np.array_equal(vision.crop_box(img, -50, -50, 10, 10), img)


def test_mean_luminance_bounds() -> None:
    """``mean_luminance`` returns 0 for black, ~255 for white, BT.709 for pure R."""
    white = np.full((4, 4, 3), 255, dtype=np.uint8)
    red = np.zeros((4, 4, 3), dtype=np.uint8)
    red[..., 0] = 255
    assert vision.mean_luminance(np.zeros((4, 4, 3), dtype=np.uint8)) == 0.0
    assert abs(vision.mean_luminance(white) - 255.0) < 1e-3
    assert abs(vision.mean_luminance(red) - 0.2126 * 255) < 1e-2


def test_top_class_argmax_labels_and_softmax() -> None:
    """``top_class`` returns the argmax, its label, and (optionally) a softmax prob."""
    scores = np.array([[0.1, 2.0, 0.3]], dtype=np.float32)
    index, label, conf = vision.top_class(scores, ["a", "b", "c"])
    assert (index, label) == (1, "b")
    assert abs(conf - 2.0) < 1e-5
    # No labels → fallback name.
    assert vision.top_class(scores)[1] == "class_1"
    # Softmax → probability in [0, 1].
    _, _, prob = vision.top_class(scores, apply_softmax=True)
    assert 0.0 < prob < 1.0


class _FakeTask:
    """A stand-in ort_vision_sdk task recording what ``async_predict`` received."""

    def __init__(self) -> None:
        self.received: object = None

    async def async_predict(self, image: object, **_kwargs: object) -> list[str]:
        self.received = image
        return ["result"]


@pytest.mark.asyncio
async def test_task_predict_decodes_encoded_source_on_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On device, encoded bytes are decoded to an array before the SDK task runs."""
    monkeypatch.setattr(vision, "on_device", lambda: True)
    decoded_from: dict[str, object] = {}

    async def _fake_decode(source: object, **_kw: object) -> np.ndarray:
        decoded_from["source"] = source
        return np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr(vision, "decode_image", _fake_decode)
    fake = _FakeTask()
    out = await vision.Detector(fake).predict(b"jpeg-bytes")
    assert decoded_from["source"] == b"jpeg-bytes"
    assert isinstance(fake.received, np.ndarray)  # the task got the decoded array
    assert out == ["result"]


@pytest.mark.asyncio
async def test_task_predict_passes_bytes_through_on_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On desktop the SDK decodes in-process, so bytes pass straight through."""
    monkeypatch.setattr(vision, "on_device", lambda: False)
    fake = _FakeTask()
    await vision.Classifier(fake).predict(b"raw")
    assert fake.received == b"raw"


@pytest.mark.asyncio
async def test_task_predict_array_is_never_decoded_on_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already-decoded array is forwarded as-is (no decode) on any platform."""
    monkeypatch.setattr(vision, "on_device", lambda: True)
    fake = _FakeTask()
    arr = np.ones((3, 3, 3), dtype=np.uint8)
    await vision.Segmenter(fake).predict(arr)
    assert fake.received is arr
