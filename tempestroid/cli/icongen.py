"""Generate the launcher icon + boot splash from one source image (`tempest icon`).

Point it at any image (a logo, a mark) and it produces the two PNGs that
``tempest build`` consumes:

* ``icon.png`` — a square launcher icon (the source center-cropped + resized).
* ``splash.png`` — the source centered on a transparent canvas (so the
  ``--splash-bg`` colour shows behind it), sized to cover the boot screen.

Then::

    tempest build --icon icon.png --splash splash.png --splash-bg "#0b0f14"

Pillow does the resizing; it is an **optional** dependency (``pip install
tempestroid[icons]``) imported lazily, so the rest of the CLI never needs it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["GeneratedAssets", "generate_assets"]


@dataclass(frozen=True)
class GeneratedAssets:
    """The files written by :func:`generate_assets`.

    Attributes:
        icon: Path to the generated square launcher icon PNG.
        splash: Path to the generated splash PNG (transparent background).
    """

    icon: Path
    splash: Path


def _require_pillow() -> Any:  # noqa: ANN401 - Pillow ships incomplete stubs
    """Import Pillow's ``Image`` module lazily, with an actionable error.

    Returns:
        The ``PIL.Image`` module (typed ``Any`` — Pillow ships incomplete stubs,
        so strict typing would otherwise flag every call).

    Raises:
        RuntimeError: If Pillow is not installed.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised via the CLI
        raise RuntimeError(
            "Pillow is required for `tempest icon`. Install it with "
            "`pip install tempestroid[icons]` (or `uv add tempestroid[icons]`)."
        ) from exc
    return Image


def _center_square(image: Any) -> Any:  # noqa: ANN401 - PIL.Image.Image (no stubs)
    """Crop an image to a centered square (the largest that fits).

    Args:
        image: The source ``PIL.Image.Image``.

    Returns:
        A square crop centered on the source.
    """
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def generate_assets(
    source: str | Path,
    out_dir: str | Path,
    *,
    icon_size: int = 512,
    splash_size: int = 1024,
    splash_scale: float = 0.5,
) -> GeneratedAssets:
    """Generate ``icon.png`` + ``splash.png`` from one source image.

    The icon is the source center-cropped to a square and resized to
    ``icon_size``. The splash is the source scaled to ``splash_scale`` of a
    ``splash_size`` transparent square canvas and centered, so the build's
    ``--splash-bg`` colour shows behind it.

    Args:
        source: Path to the source image (any Pillow-readable format).
        out_dir: Directory to write ``icon.png`` and ``splash.png`` into
            (created if missing).
        icon_size: The square launcher-icon edge in pixels.
        splash_size: The square splash canvas edge in pixels.
        splash_scale: The fraction of the splash canvas the source mark occupies
            (0–1).

    Returns:
        The :class:`GeneratedAssets` paths.

    Raises:
        RuntimeError: If Pillow is not installed.
        FileNotFoundError: If ``source`` does not exist.
        ValueError: If ``splash_scale`` is not in ``(0, 1]``.
    """
    if not 0.0 < splash_scale <= 1.0:
        raise ValueError(f"splash_scale must be in (0, 1], got {splash_scale}")
    src = Path(source).expanduser()
    if not src.is_file():
        raise FileNotFoundError(f"source image not found: {src}")
    image_cls = _require_pillow()

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with image_cls.open(src) as raw:
        source_rgba = raw.convert("RGBA")

    # Icon: largest centered square, resized to a single square PNG. The build's
    # --icon copies this one file to every mipmap density, so one size suffices.
    icon_img = _center_square(source_rgba).resize(
        (icon_size, icon_size), image_cls.LANCZOS
    )
    icon_path = out / "icon.png"
    icon_img.save(icon_path, format="PNG")

    # Splash: the source scaled to `splash_scale` of the canvas, centered on a
    # transparent square so the --splash-bg colour shows through behind it.
    mark = source_rgba.copy()
    target = max(1, int(splash_size * splash_scale))
    mark.thumbnail((target, target), image_cls.LANCZOS)
    canvas = image_cls.new("RGBA", (splash_size, splash_size), (0, 0, 0, 0))
    offset = ((splash_size - mark.width) // 2, (splash_size - mark.height) // 2)
    canvas.paste(mark, offset, mark)
    splash_path = out / "splash.png"
    canvas.save(splash_path, format="PNG")

    return GeneratedAssets(icon=icon_path, splash=splash_path)
