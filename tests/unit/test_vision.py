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
