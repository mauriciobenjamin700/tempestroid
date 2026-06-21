# pyright: reportPrivateUsage=false
"""Qt renderer tests for the H6 research / data-science components.

Charts (LineChart/BarChart) lower to a sized ``Canvas``; DetectionOverlay lowers
to a ``Stack`` of an ``Image`` + a sized ``Canvas`` overlay. Both rely on the
Canvas keeping its ``width``/``height`` props as a pinned widget size inside a
box layout (``_pin_canvas_size``) and, for the overlay, the stack folding those
props into the layer style (``_relayout_stack``) so the box-drawing Canvas fills
the image instead of collapsing to a zero sizeHint. These tests pin both fixes +
that the compositional components (MetricCard/ConfidenceBadge) lower + mount.
"""

from __future__ import annotations

from tempest_core.components import (
    BarChart,
    ChartSeries,
    ConfidenceBadge,
    DetectionBox,
    DetectionOverlay,
    LineChart,
    MetricCard,
)
from tempest_core.core.reconciler import build

from tempestroid.renderers.qt.renderer import QtRenderer, _CanvasWidget


def test_barchart_canvas_keeps_its_pinned_size(qapp: object) -> None:
    """A ``BarChart`` lowers to a Canvas pinned to its width/height.

    Regression guard: ``_apply_sizing`` resets unset-``Style`` widgets to a
    flexible range, so the Canvas size must be re-pinned afterwards or the chart
    collapses to nothing inside a box layout.
    """
    renderer = QtRenderer()
    renderer.mount(
        build(BarChart(values=[0.8, 0.4, 0.2], labels=["a", "b", "c"],
                       width=480.0, height=160.0))
    )
    canvas = renderer.host.findChild(_CanvasWidget)
    assert isinstance(canvas, _CanvasWidget)
    assert canvas.minimumWidth() == 480
    assert canvas.minimumHeight() == 160
    assert canvas.maximumWidth() == 480


def test_linechart_lowers_to_canvas_with_commands(qapp: object) -> None:
    """A ``LineChart`` lowers to a Canvas carrying draw commands."""
    node = build(
        LineChart(
            series=[ChartSeries(points=[920.0, 880.0, 860.0], label="ms")],
            width=480.0,
            height=160.0,
        )
    )
    assert node.type == "Canvas"
    assert node.props["commands"]
    QtRenderer().mount(node)


def test_detection_overlay_box_canvas_is_sized(qapp: object) -> None:
    """The DetectionOverlay box-Canvas fills the stack (not a zero sizeHint).

    Regression guard: the overlay Canvas carries its extent in width/height props
    (not Style); the stack must fold them into the layer style so the box Canvas
    overlays the image at full size instead of collapsing.
    """
    renderer = QtRenderer()
    renderer.mount(
        build(
            DetectionOverlay(
                image_src="x.jpg",
                boxes=[DetectionBox(x1=0.2, y1=0.3, x2=0.8, y2=0.7,
                                    name="cat", conf=0.9)],
                width=320.0,
                height=240.0,
            )
        )
    )
    canvas = renderer.host.findChild(_CanvasWidget)
    assert isinstance(canvas, _CanvasWidget)
    # The box-overlay Canvas is laid out at the stack's full extent, not 0x0.
    assert canvas.width() >= 240
    assert canvas.height() >= 180


def test_metric_card_and_confidence_badge_lower_and_mount(qapp: object) -> None:
    """MetricCard + ConfidenceBadge compose existing components and mount."""
    renderer = QtRenderer()
    renderer.mount(build(MetricCard(label="Detections", value="2", delta="+1",
                                    delta_up=True, color_scheme="primary")))
    renderer.mount(build(ConfidenceBadge(confidence=0.84, label="banana")))
