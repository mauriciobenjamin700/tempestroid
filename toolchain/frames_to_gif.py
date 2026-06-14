"""Assemble PNG frames into a small, looped animated GIF.

Used by ``capture_gif.sh`` to turn a burst of on-device screencaps of an
*animated* tempestroid example (``animation``, ``gestures``, ``stopwatch``…)
into a single ``.gif`` for the docs gallery — a static ``.png`` cannot show the
animation. Pillow only (already in the dev env); no system ImageMagick needed.
"""

from __future__ import annotations

import glob
import os
import sys

from PIL import Image


def assemble(
    frames_dir: str,
    out_path: str,
    *,
    width: int = 360,
    duration_ms: int = 250,
) -> int:
    """Combine the PNG frames in ``frames_dir`` into a looped GIF at ``out_path``.

    Args:
        frames_dir: Directory holding the captured ``*.png`` frames (sorted by
            name = capture order).
        out_path: Destination ``.gif`` path.
        width: Target width in pixels; frames are downscaled (aspect kept) to
            keep the doc asset light.
        duration_ms: Per-frame display duration in milliseconds.

    Returns:
        The number of frames written into the GIF.

    Raises:
        SystemExit: If no PNG frames are found in ``frames_dir``.
    """
    paths: list[str] = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
    if not paths:
        raise SystemExit(f"no PNG frames in {frames_dir}")

    frames: list[Image.Image] = []
    for path in paths:
        img: Image.Image = Image.open(path).convert("RGB")
        height: int = int(img.height * width / img.width)
        frames.append(img.resize((width, height)))

    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return len(frames)


def main() -> None:
    """CLI entry: ``frames_to_gif.py <frames_dir> <out.gif>``."""
    if len(sys.argv) != 3:
        raise SystemExit("usage: frames_to_gif.py <frames_dir> <out.gif>")
    count: int = assemble(sys.argv[1], sys.argv[2])
    print(f"wrote {sys.argv[2]} ({count} frames)")


if __name__ == "__main__":
    main()
