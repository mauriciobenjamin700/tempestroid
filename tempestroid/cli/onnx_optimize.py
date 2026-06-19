"""Host-side ONNX model optimization for on-device inference (Trilho G3).

The device runs models through the native ``onnxruntime-android`` AAR (see
:mod:`tempestroid.native.inference`). Before shipping a model, optimize it on the
**host** (build time) to shrink the APK and speed inference:

* **INT8 dynamic quantization** — ``onnxruntime.quantization.quantize_dynamic``
  quantizes the weights to 8-bit, typically ~4x smaller with little accuracy loss
  for CNNs; the ORT CPU EP runs the quantized ops natively.
* **fp16** — half-precision weights (optional; needs ``onnxconverter-common``).
* **``.ort`` format** — ``onnxruntime``'s mobile format
  (``convert_onnx_models_to_ort``): loads faster and pairs with minimal/mobile
  builds. The full Android AAR loads both ``.onnx`` and ``.ort``.

This is pure build-time tooling — it never runs on device. Exposed as
``tempest optimize`` (gated on the ``[vision]`` extra: ``onnx`` + ``onnxruntime``).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = ["OptimizeResult", "Quantization", "optimize_model"]

#: The supported weight quantization modes.
Quantization = Literal["none", "int8", "fp16"]


def _empty_sizes() -> dict[str, int]:
    """Build the empty sizes map (a typed ``default_factory`` for the dataclass).

    Returns:
        An empty ``{label: bytes}`` mapping.
    """
    return {}


@dataclass
class OptimizeResult:
    """The artifacts produced by :func:`optimize_model`.

    Attributes:
        source: The input ``.onnx`` model.
        quantized: The quantized ``.onnx`` (INT8/fp16), or ``None`` when
            ``quantize="none"``.
        ort: The converted ``.ort`` model, or ``None`` when ``to_ort`` is False.
        sizes: Byte sizes keyed by artifact label (``"source"``, ``"quantized"``,
            ``"ort"``) for the size-win report.
    """

    source: Path
    quantized: Path | None = None
    ort: Path | None = None
    sizes: dict[str, int] = field(default_factory=_empty_sizes)

    @property
    def shipped(self) -> Path:
        """The artifact to ship: ``.ort`` if built, else quantized, else source."""
        return self.ort or self.quantized or self.source


def _quantize_int8(source: Path, dest: Path) -> None:
    """Dynamically quantize ``source`` weights to INT8 into ``dest``.

    Args:
        source: The input ``.onnx`` model.
        dest: The output quantized ``.onnx`` path.

    Raises:
        RuntimeError: If ``onnxruntime.quantization`` is unavailable.
    """
    # onnxruntime.quantization is untyped third-party tooling; access it through
    # an explicit ``Any`` module so the call boundary stays type-clean without
    # fragile per-line stub ignores.
    try:
        quant: Any = importlib.import_module("onnxruntime.quantization")
    except ImportError as exc:  # pragma: no cover - import-gated
        raise RuntimeError(
            "INT8 quantization needs onnx + onnxruntime — install the vision "
            "extra: pip install tempestroid[vision]."
        ) from exc
    quant.quantize_dynamic(source, dest, weight_type=quant.QuantType.QInt8)


def _quantize_fp16(source: Path, dest: Path) -> None:
    """Convert ``source`` weights to fp16 into ``dest``.

    Args:
        source: The input ``.onnx`` model.
        dest: The output fp16 ``.onnx`` path.

    Raises:
        RuntimeError: If ``onnx``/``onnxconverter-common`` are unavailable.
    """
    # onnx + onnxconverter-common are untyped (and the latter is an optional
    # extra); access both as ``Any`` modules, guarded by the try/except.
    try:
        onnx: Any = importlib.import_module("onnx")
        float16: Any = importlib.import_module("onnxconverter_common.float16")
    except ImportError as exc:
        raise RuntimeError(
            "fp16 conversion needs onnxconverter-common: pip install "
            "onnxconverter-common (onnx comes with the vision extra)."
        ) from exc
    model = onnx.load(str(source))
    onnx.save(float16.convert_float_to_float16(model), str(dest))


def _convert_to_ort(source: Path, out_dir: Path) -> Path:
    """Convert ``source`` to ORT mobile (``.ort``) format in ``out_dir``.

    Invokes ``onnxruntime.tools.convert_onnx_models_to_ort`` (Fixed optimization
    style) via the current interpreter, then locates the produced ``.ort``.

    Args:
        source: The input ``.onnx`` model (already quantized, if requested).
        out_dir: Directory the ``.ort`` is written to.

    Returns:
        The produced ``.ort`` path.

    Raises:
        RuntimeError: If the conversion fails or no ``.ort`` is produced.
    """
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "onnxruntime.tools.convert_onnx_models_to_ort",
            str(source),
            "--output_dir",
            str(out_dir),
            "--optimization_style",
            "Fixed",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"onnx → ort conversion failed (rc={result.returncode}):\n{result.stderr}"
        )
    candidates = sorted(out_dir.glob("*.ort"))
    if not candidates:
        raise RuntimeError(f"conversion produced no .ort in {out_dir}")
    # The converter names it "<stem>.ort" / "<stem>.optimized.ort"; prefer the
    # one matching the source stem.
    for candidate in candidates:
        if candidate.stem.startswith(source.stem):
            return candidate
    return candidates[0]


def optimize_model(
    source: str | Path,
    *,
    out_dir: str | Path | None = None,
    quantize: Quantization = "int8",
    to_ort: bool = True,
) -> OptimizeResult:
    """Optimize an ONNX model for on-device inference (host build-time step).

    Quantizes (optional) then converts to ``.ort`` (optional), writing artifacts
    next to the source (or into ``out_dir``) and reporting byte sizes.

    Args:
        source: Path to the input ``.onnx`` model.
        out_dir: Directory for the artifacts; defaults to the source's directory.
        quantize: Weight quantization — ``"int8"`` (default, smallest),
            ``"fp16"``, or ``"none"``.
        to_ort: Also convert to the ``.ort`` mobile format (default ``True``).

    Returns:
        An :class:`OptimizeResult` with the produced paths and their sizes.

    Raises:
        FileNotFoundError: If ``source`` does not exist.
        RuntimeError: If a required tool is missing or a step fails.
    """
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"model not found: {source_path}")
    target_dir = Path(out_dir) if out_dir is not None else source_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    result = OptimizeResult(source=source_path)
    result.sizes["source"] = source_path.stat().st_size

    model_for_ort = source_path
    if quantize == "int8":
        quantized = target_dir / f"{source_path.stem}.int8.onnx"
        _quantize_int8(source_path, quantized)
        result.quantized = quantized
        result.sizes["quantized"] = quantized.stat().st_size
        model_for_ort = quantized
    elif quantize == "fp16":
        quantized = target_dir / f"{source_path.stem}.fp16.onnx"
        _quantize_fp16(source_path, quantized)
        result.quantized = quantized
        result.sizes["quantized"] = quantized.stat().st_size
        model_for_ort = quantized

    if to_ort:
        ort_path = _convert_to_ort(model_for_ort, target_dir)
        result.ort = ort_path
        result.sizes["ort"] = ort_path.stat().st_size

    return result
