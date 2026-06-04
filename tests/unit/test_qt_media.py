# Phase E7 (media + graphics) Qt renderer coverage. Reaches into the renderer's
# private widget classes to assert the canvas/clip backing widgets — internal by
# design, mirroring the rest of the Qt renderer test suite.
# pyright: reportPrivateUsage=false
from typing import cast

import pytest
from PySide6.QtWidgets import QGraphicsBlurEffect, QLabel, QWidget

from tempestroid import (
    ArcTo,
    BackdropFilter,
    Blur,
    CameraPreview,
    Canvas,
    ClipPath,
    ClipShape,
    Close,
    Container,
    DrawOval,
    DrawRect,
    DrawText,
    FillCmd,
    LineTo,
    MapView,
    MoveTo,
    QrScanner,
    StrokeCmd,
    Svg,
    Text,
    VideoPlayer,
    WebView,
    build,
)
from tempestroid.renderers.qt import QtRenderer
from tempestroid.renderers.qt.renderer import _CanvasWidget, _ClipWidget
from tempestroid.widgets import DrawCommand, Widget

pytestmark = pytest.mark.usefixtures("qapp")


def _all_commands() -> list[DrawCommand]:
    """Return one instance of every ``DrawCommand`` kind for canvas coverage."""
    return [
        MoveTo(x=0.0, y=0.0),
        LineTo(x=10.0, y=10.0),
        ArcTo(x=0.0, y=0.0, width=5.0, height=5.0, start_angle=0.0, sweep_angle=90.0),
        Close(),
        DrawRect(x=0.0, y=0.0, width=20.0, height=10.0),
        DrawOval(x=0.0, y=0.0, width=8.0, height=8.0),
        FillCmd(color=[1.0, 0.0, 0.0, 1.0]),
        StrokeCmd(color=[0.0, 0.0, 1.0, 1.0], width=2.0),
        DrawText(text="hi", x=2.0, y=8.0, size=12.0, color=[0.0, 0.0, 0.0, 1.0]),
    ]


def test_canvas_renders_all_command_kinds_without_error() -> None:
    """A Canvas with every draw-command kind mounts and paints headlessly."""
    renderer = QtRenderer()
    renderer.mount(build(Canvas(commands=_all_commands(), width=120.0, height=80.0)))
    widget = cast("_CanvasWidget", renderer.root_widget)
    assert isinstance(widget, _CanvasWidget)
    # Commands are lowered to plain JSON-able dicts (never the IR models).
    assert all(isinstance(cmd, dict) for cmd in widget._commands)
    assert {cmd["kind"] for cmd in widget._commands} == {
        "move_to",
        "line_to",
        "arc_to",
        "close",
        "draw_rect",
        "draw_oval",
        "fill",
        "stroke",
        "draw_text",
    }
    # The optional fixed size is honoured.
    assert widget.width() == 120
    assert widget.height() == 80
    widget.show()
    widget.repaint()  # force the paintEvent — must not raise


def test_canvas_update_replaces_commands() -> None:
    """Updating the command list re-paints with the new commands."""
    renderer = QtRenderer()
    renderer.mount(build(Canvas(commands=[DrawRect(x=0, y=0, width=4, height=4)])))
    widget = cast("_CanvasWidget", renderer.root_widget)
    assert len(widget._commands) == 1
    widget.set_commands([{"kind": "fill", "color": [0.0, 1.0, 0.0, 1.0]}])
    assert widget._commands == [{"kind": "fill", "color": [0.0, 1.0, 0.0, 1.0]}]


def test_video_player_mounts() -> None:
    """A VideoPlayer mounts (real backend or placeholder) without raising."""
    renderer = QtRenderer()
    renderer.mount(
        build(
            VideoPlayer(
                src="https://example.com/clip.mp4",
                autoplay=False,
                loop=True,
                muted=True,
            )
        )
    )
    assert isinstance(renderer.root_widget, QWidget)


def test_web_view_mounts() -> None:
    """A WebView mounts (QWebEngineView or placeholder) without raising."""
    renderer = QtRenderer()
    renderer.mount(build(WebView(url="https://example.com", javascript_enabled=True)))
    assert isinstance(renderer.root_widget, QWidget)


def test_svg_falls_back_to_source_text_when_missing() -> None:
    """A missing/invalid SVG source shows the source string instead of crashing."""
    renderer = QtRenderer()
    renderer.mount(build(Svg(src="does-not-exist.svg")))
    label = cast("QLabel", renderer.root_widget)
    assert isinstance(label, QLabel)
    assert label.text() == "does-not-exist.svg"


def test_svg_remote_source_shows_url_text() -> None:
    """A remote SVG source is not fetched by the simulator (shows the URL)."""
    renderer = QtRenderer()
    renderer.mount(build(Svg(src="https://example.com/logo.svg")))
    label = cast("QLabel", renderer.root_widget)
    assert label.text() == "https://example.com/logo.svg"


def test_blur_applies_graphics_blur_effect() -> None:
    """A Blur wrapper applies a QGraphicsBlurEffect with the requested radius."""
    renderer = QtRenderer()
    renderer.mount(build(Blur(radius=12.0, child=Container(child=Text(content="x")))))
    effect = renderer.root_widget.graphicsEffect()
    assert isinstance(effect, QGraphicsBlurEffect)
    assert effect.blurRadius() == 12.0
    # The wrapped child still mounts under the wrapper.
    labels = [label.text() for label in renderer.root_widget.findChildren(QLabel)]
    assert "x" in labels


def test_backdrop_filter_applies_blur_effect() -> None:
    """BackdropFilter is approximated as a blur of the child (documented Qt limit)."""
    renderer = QtRenderer()
    renderer.mount(build(BackdropFilter(radius=5.0, child=Container())))
    effect = renderer.root_widget.graphicsEffect()
    assert isinstance(effect, QGraphicsBlurEffect)
    assert effect.blurRadius() == 5.0


@pytest.mark.parametrize(
    "shape",
    [ClipShape.CIRCLE, ClipShape.OVAL, ClipShape.ROUNDED_RECT],
)
def test_clip_path_masks_without_error(shape: ClipShape) -> None:
    """A ClipPath wrapper sets a non-null mask for each supported shape."""
    renderer = QtRenderer()
    renderer.mount(build(ClipPath(shape=shape, radius=10.0, child=Container())))
    widget = cast("_ClipWidget", renderer.root_widget)
    assert isinstance(widget, _ClipWidget)
    widget.resize(80, 80)
    widget.show()
    # A mask region is installed once the widget has a non-zero size.
    assert not widget.mask().isEmpty()


@pytest.mark.parametrize(
    ("widget", "expected"),
    [
        (CameraPreview(), "[CameraPreview — device only]"),
        (QrScanner(), "[QrScanner — device only]"),
        (MapView(latitude=1.0, longitude=2.0), "[MapView — device only]"),
    ],
)
def test_device_only_widgets_show_placeholder(widget: Widget, expected: str) -> None:
    """Device-only widgets render an explicit placeholder label in the simulator."""
    renderer = QtRenderer()
    renderer.mount(build(widget))
    label = cast("QLabel", renderer.root_widget)
    assert isinstance(label, QLabel)
    assert label.text() == expected
