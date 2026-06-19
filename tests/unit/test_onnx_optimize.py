"""Tests for the G3 host model-optimization tooling (``cli/onnx_optimize.py``).

Skipped unless the vision extra (``onnx`` + ``onnxruntime``) is installed. Uses
the bundled squeezenet1.1 model to exercise the real INT8 → ``.ort`` pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("onnx")
pytest.importorskip("onnxruntime.quantization")

from tempestroid.cli.onnx_optimize import optimize_model  # noqa: E402

_MODEL = Path(__file__).resolve().parents[2] / "examples/visionspike/squeezenet1.1.onnx"

pytestmark = pytest.mark.skipif(
    not _MODEL.is_file(), reason="bundled squeezenet1.1.onnx not present"
)


def test_int8_quantize_and_ort_shrink(tmp_path: Any) -> None:
    """INT8 + .ort produces both artifacts, each smaller than the source."""
    result = optimize_model(_MODEL, out_dir=tmp_path, quantize="int8", to_ort=True)

    assert result.quantized is not None and result.quantized.is_file()
    assert result.ort is not None and result.ort.is_file()
    assert result.ort.suffix == ".ort"
    # INT8 weights are ~4x smaller; the shipped artifact is the .ort.
    assert result.sizes["quantized"] < result.sizes["source"]
    assert result.shipped == result.ort
    assert result.sizes["ort"] < result.sizes["source"]


def test_no_quantize_still_converts_to_ort(tmp_path: Any) -> None:
    """``quantize='none'`` skips quantization but still emits a .ort."""
    result = optimize_model(_MODEL, out_dir=tmp_path, quantize="none", to_ort=True)

    assert result.quantized is None
    assert result.ort is not None and result.ort.is_file()
    assert result.shipped == result.ort


def test_quantize_only_no_ort(tmp_path: Any) -> None:
    """``to_ort=False`` yields the quantized .onnx as the shipped artifact."""
    result = optimize_model(_MODEL, out_dir=tmp_path, quantize="int8", to_ort=False)

    assert result.ort is None
    assert result.quantized is not None
    assert result.shipped == result.quantized


def test_missing_model_raises() -> None:
    """A non-existent source raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        optimize_model("/nonexistent/model.onnx", quantize="none", to_ort=False)
