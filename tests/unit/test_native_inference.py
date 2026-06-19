"""Unit tests for the on-device ONNX backend (Trilho G, ``native/inference.py``).

A fake ``send_native_request`` stands in for the Kotlin ``onnx`` host module, so
the full marshal path — encode tensor → bridge ``load``/``infer`` → decode tensor
— is exercised in-process with no device. The final test drives a real
ort-vision-sdk ``Detector`` through the backend (skipped if the SDK is absent),
proving the published 0.4.0 ``InferenceBackend`` contract holds end to end.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from tempestroid.native import inference
from tempestroid.native.inference import AarBackend, decode_tensor, encode_tensor


def _fake_host(infer_outputs: list[np.ndarray]) -> Any:
    """Build a fake ``send_native_request`` simulating the Kotlin ``onnx`` module.

    Args:
        infer_outputs: The arrays the fake host returns for an ``infer`` call.

    Returns:
        An async callable with the ``send_native_request`` signature.
    """

    async def fake_send(
        module: str, action: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        assert module == "onnx"
        if action == "load":
            return {
                "session_id": "sess-1",
                "input_names": ["images"],
                "input_shapes": [[1, 3, 640, 640]],
                "output_names": ["output0"],
                "output_shapes": [[1, 84, 8400]],
            }
        if action == "infer":
            # Echo the canned outputs; record the received inputs for assertions.
            fake_send.last_args = args  # type: ignore[attr-defined]
            return {"outputs": [encode_tensor(o) for o in infer_outputs]}
        raise AssertionError(f"unexpected action {action!r}")

    return fake_send


def test_encode_decode_round_trip() -> None:
    """A tensor survives encode → JSON-able dict → decode unchanged."""
    arr = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
    envelope = encode_tensor(arr)
    assert envelope["dtype"] == "float32"
    assert envelope["shape"] == [2, 3, 4]
    assert isinstance(envelope["data"], str)  # base64 text (JSON-able)
    restored = decode_tensor(envelope)
    assert np.array_equal(restored, arr)
    assert restored.dtype == arr.dtype


async def test_create_fetches_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """``AarBackend.create`` loads the model and exposes its metadata."""
    monkeypatch.setattr(inference, "send_native_request", _fake_host([]))
    backend = await AarBackend.create("model.onnx")
    assert backend.session_id == "sess-1"
    assert backend.input_name == "images"
    assert backend.input_shape == (1, 3, 640, 640)
    assert backend.output_names == ["output0"]
    assert backend.output_shapes == [(1, 84, 8400)]


async def test_async_run_bridges_tensors(monkeypatch: pytest.MonkeyPatch) -> None:
    """``async_run`` encodes the input, bridges, and decodes the output."""
    out = np.full((1, 84, 8400), 0.5, dtype=np.float32)
    fake = _fake_host([out])
    monkeypatch.setattr(inference, "send_native_request", fake)
    backend = await AarBackend.create("model.onnx")

    feeds = {"images": np.zeros((1, 3, 640, 640), dtype=np.float32)}
    outputs = await backend.async_run(feeds)
    assert len(outputs) == 1
    assert np.array_equal(outputs[0], out)
    # The input crossed the bridge as a base64 tensor envelope.
    sent = fake.last_args["inputs"]["images"]  # type: ignore[attr-defined]
    assert sent["shape"] == [1, 3, 640, 640]
    assert decode_tensor(sent).shape == (1, 3, 640, 640)


async def test_run_on_loop_thread_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync ``run`` on the app loop thread refuses (cannot block the loop)."""
    monkeypatch.setattr(inference, "send_native_request", _fake_host([]))
    backend = await AarBackend.create("model.onnx")
    with pytest.raises(RuntimeError, match="cannot block the app loop"):
        backend.run({"images": np.zeros((1, 3, 640, 640), dtype=np.float32)})


async def test_detector_through_aar_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real ort-vision-sdk ``Detector`` runs through the AAR backend loopback.

    Proves the published 0.4.0 ``InferenceBackend`` contract: pre/post run in
    Python (NumPy) while inference is bridged. Skipped if the SDK is not
    installed (it is an opt-in ``[vision]`` extra).
    """
    pytest.importorskip("ort_vision_sdk")
    from ort_vision_sdk import DetectionResults, Detector, InferenceBackend

    out = np.zeros((1, 84, 8400), dtype=np.float32)  # YOLO (4+80, N), no detections
    monkeypatch.setattr(inference, "send_native_request", _fake_host([out]))
    backend = await AarBackend.create("model.onnx")

    assert isinstance(backend, InferenceBackend)  # structural protocol check
    det = Detector("model.onnx", backend=backend)
    assert len(det.labels) == 80  # num_classes inferred from output_shapes

    results = await det.ort_async_predict(np.zeros((120, 160, 3), dtype=np.uint8))
    assert isinstance(results, list)
    assert isinstance(results[0], DetectionResults)
