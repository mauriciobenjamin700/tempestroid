"""Compare a captured screenshot against a versioned golden image (F8).

The emulator-verify flow captures one screenshot per example; this pins those
captures against golden PNGs under ``docs/assets/emulator/golden/`` so a visual
regression in the Compose renderer fails the gate instead of going unnoticed.
Complements the JVM Roborazzi goldens (F7 camada B) and the phase-D conformance
suite: those pin the ``Style`` translation, this pins the end-to-end on-emulator
render. Pillow only (already in the dev env); no system ImageMagick needed.

A first run with ``--update`` (or a missing golden) writes the golden and
passes, so capturing the baseline is a normal part of the flow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops


def diff_ratio(actual_path: str, golden_path: str) -> float:
    """Return the fraction of pixels that differ between two images.

    Both images are converted to RGB and the actual is resized to the golden's
    size (so a device-density difference does not by itself fail the check). The
    ratio is ``differing_pixels / total_pixels`` over the absolute per-pixel
    difference — 0.0 means identical, 1.0 means every pixel differs.

    Args:
        actual_path: Path to the freshly captured screenshot.
        golden_path: Path to the versioned golden image.

    Returns:
        The differing-pixel ratio in ``[0.0, 1.0]``.
    """
    actual: Image.Image = Image.open(actual_path).convert("RGB")
    golden: Image.Image = Image.open(golden_path).convert("RGB")
    if actual.size != golden.size:
        actual = actual.resize(golden.size)
    # Per-pixel difference → grayscale → histogram. Bucket 0 counts pixels that
    # are identical (zero difference); everything above it differs. Using the
    # histogram (a typed list[int]) avoids iterating raw pixel data and is fast.
    gray_diff: Image.Image = ImageChops.difference(actual, golden).convert("L")
    histogram: list[int] = gray_diff.histogram()
    total: int = sum(histogram)
    differing: int = total - histogram[0]
    return differing / total if total else 0.0


def compare(
    actual_path: str,
    golden_path: str,
    *,
    tolerance: float = 0.02,
    update: bool = False,
) -> bool:
    """Compare ``actual`` to ``golden``, updating or creating the golden if asked.

    Args:
        actual_path: Path to the freshly captured screenshot.
        golden_path: Path to the versioned golden image.
        tolerance: Maximum allowed differing-pixel ratio before failing.
        update: Overwrite (or create) the golden from ``actual`` and pass.

    Returns:
        ``True`` when within tolerance (or updated/created), ``False`` otherwise.
    """
    golden = Path(golden_path)
    if update or not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        Image.open(actual_path).convert("RGB").save(golden)
        reason: str = "updated" if golden.exists() else "created"
        print(f"golden {reason}: {golden_path}")
        return True
    ratio: float = diff_ratio(actual_path, golden_path)
    ok: bool = ratio <= tolerance
    verdict: str = "PASS" if ok else "FAIL"
    print(f"visual {verdict}: diff={ratio:.4f} tol={tolerance:.4f} ({golden_path})")
    return ok


def main() -> None:
    """CLI entry point.

    Usage::

        visual_regression.py <actual.png> <golden.png> [--tolerance T] [--update]
    """
    parser = argparse.ArgumentParser(description="Compare a screenshot to a golden.")
    parser.add_argument("actual", help="freshly captured screenshot PNG")
    parser.add_argument("golden", help="versioned golden PNG")
    parser.add_argument("--tolerance", type=float, default=0.02)
    parser.add_argument("--update", action="store_true", help="write the golden + pass")
    args = parser.parse_args()
    ok: bool = compare(
        args.actual, args.golden, tolerance=args.tolerance, update=args.update
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
