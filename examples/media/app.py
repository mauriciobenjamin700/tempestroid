"""Media & graphics demo — Canvas drawing, SVG, blur and clip (E7).

Showcases the phase-E7 widgets that render identically (or near-identically)
across both renderers:

- :class:`~tempestroid.Canvas` — a drawing surface fed a serializable list of
  draw commands (rects, ovals, text, fill/stroke); the same command list draws
  the same chart in Qt (`QPainter`) and Compose (`drawIntoCanvas`).
- :class:`~tempestroid.Svg` — render an inline SVG.
- :class:`~tempestroid.Blur` + :class:`~tempestroid.ClipPath` — blur a child and
  clip it to a shape.

Heavier media leaves (`VideoPlayer`, `WebView`, `CameraPreview`, `QrScanner`,
`MapView`) exist too; some render as a placeholder in the Qt simulator (see the
phase notes) and are device-only.

Run it in the Qt simulator with the ``qt`` extra installed::

    uv run python examples/media/app.py

Or on a device via code-push::

    uv run tempest serve examples/media/app.py
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestroid import (
    Blur,
    Canvas,
    ClipPath,
    ClipShape,
    Color,
    Column,
    DrawRect,
    DrawText,
    Edge,
    FillCmd,
    Style,
    Text,
    Widget,
)
from tempestroid.core.state import App

_BARS = [40.0, 90.0, 60.0, 120.0, 75.0]
_COLORS = [
    [0.42, 0.30, 0.94, 1.0],
    [0.18, 0.62, 0.40, 1.0],
    [0.90, 0.55, 0.10, 1.0],
    [0.85, 0.25, 0.30, 1.0],
    [0.20, 0.50, 0.90, 1.0],
]


@dataclass
class MediaState:
    """The demo has no mutable state; the drawing is static."""


def make_state() -> MediaState:
    """Build a fresh initial state.

    Returns:
        A new media state.
    """
    return MediaState()


def _chart() -> Canvas:
    """Build a small bar chart from draw commands.

    Returns:
        A canvas whose command list draws five filled bars with a baseline.
    """
    commands: list[object] = []
    for index, height in enumerate(_BARS):
        x = 10.0 + index * 44.0
        commands.append(
            DrawRect(x=x, y=140.0 - height, width=32.0, height=height)
        )
        commands.append(FillCmd(color=_COLORS[index]))
    commands.append(DrawText(text="Canvas chart", x=10.0, y=158.0, size=12.0))
    return Canvas(width=240.0, height=170.0, commands=commands)  # type: ignore[arg-type]


def view(app: App[MediaState]) -> Widget:
    """Build the media UI.

    Args:
        app: The running app (unused — the demo is static).

    Returns:
        The root widget of the media screen.
    """
    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        children=[
            Text(content="Media & graphics", style=Style(font_size=22.0)),
            _chart(),
            Text(content="Blur + ClipPath:", style=Style(font_size=16.0)),
            ClipPath(
                shape=ClipShape.CIRCLE,
                child=Blur(
                    radius=6.0,
                    child=Column(
                        style=Style(
                            padding=Edge.all(36.0),
                            background=Color.from_hex("#6c4cf0"),
                        ),
                        children=[
                            Text(
                                content="blurred",
                                style=Style(color=Color.from_hex("#ffffff")),
                            ),
                        ],
                    ),
                ),
            ),
        ],
    )


def main() -> int:
    """Run the media demo in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — media", size=(380, 640))


if __name__ == "__main__":
    raise SystemExit(main())
