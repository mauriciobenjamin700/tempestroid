"""H6 design-system gallery — research / data-science components.

A faux vision-result dashboard (the shape an `ort-vision-sdk` app produces):
a ``DetectionOverlay`` with bounding boxes over an image, a ``MetricCard`` +
``ConfidenceBadge`` summary, a ``BarChart`` of per-class confidence, a
``LineChart`` latency trend, and a ``DataTable`` of detections — every component
themed from the design-system ``Theme``, no hand-set colors.

Run in the Qt simulator::

    uv run python examples/h6gallery/app.py

Renderer-agnostic — the Qt renderer is imported lazily inside ``main`` so the
device loader (no PySide6) can import this module.
"""

from __future__ import annotations

from pathlib import Path

from tempestroid import (
    App,
    BarChart,
    ChartSeries,
    Color,
    Column,
    ConfidenceBadge,
    DataTable,
    DetectionBox,
    DetectionOverlay,
    Edge,
    FontWeight,
    HStack,
    LineChart,
    MetricCard,
    Style,
    Text,
    VStack,
    Widget,
)

#: The demo image lives beside this file (a self-contained example).
_IMAGE = str(Path(__file__).resolve().parent / "banana.jpg")

#: Faux detector output — what `Detector.predict(...)` would yield, already
#: adapted to normalized ``[0,1]`` xyxy boxes.
_BOXES: list[DetectionBox] = [
    DetectionBox(x1=0.18, y1=0.30, x2=0.82, y2=0.74, name="banana", conf=0.84),
    DetectionBox(x1=0.05, y1=0.05, x2=0.30, y2=0.22, name="apple", conf=0.41),
]


def make_state() -> dict[str, object]:
    """Build a fresh (empty) state — this gallery is static.

    Returns:
        An empty state dict (the dashboard is read-only).
    """
    return {}


def _heading(title: str, *, key: str) -> Widget:
    """Build a small uppercase section heading.

    Args:
        title: The heading text.
        key: The stable diff key.

    Returns:
        A muted, bold ``Text`` label.
    """
    return Text(
        content=title,
        style=Style(
            color=Color.from_hex("#6b7280"),
            font_size=12.0,
            font_weight=FontWeight.BOLD,
        ),
        key=key,
    )


def _section(title: str, *, key: str, body: Widget) -> Widget:
    """Build a titled section block.

    Args:
        title: The section heading.
        key: The stable diff key.
        body: The section content.

    Returns:
        A ``VStack`` with the heading above the body.
    """
    return VStack(gap="sm", key=key, children=[_heading(title, key="h"), body])


def view(app: App[dict[str, object]]) -> Widget:
    """Build the H6 research dashboard tree.

    Args:
        app: The application (state unused — the dashboard is static).

    Returns:
        The root widget.
    """
    overlay = DetectionOverlay(
        image_src=_IMAGE,
        boxes=_BOXES,
        width=320.0,
        height=240.0,
        key="overlay",
    )

    metrics = HStack(
        gap="md",
        key="metrics",
        children=[
            MetricCard(
                label="Detections",
                value=str(len(_BOXES)),
                delta="+1",
                delta_up=True,
                color_scheme="primary",
                key="m-count",
            ),
            MetricCard(
                label="Top class",
                value="banana",
                color_scheme="success",
                key="m-top",
            ),
        ],
    )

    badges = HStack(
        gap="sm",
        key="badges",
        children=[
            ConfidenceBadge(confidence=0.84, label="banana", key="cb-banana"),
            ConfidenceBadge(confidence=0.41, label="apple", key="cb-apple"),
        ],
    )

    conf_bars = BarChart(
        values=[0.84, 0.41, 0.18, 0.09],
        labels=["banana", "apple", "pear", "lemon"],
        width=480.0,
        height=160.0,
        color_scheme="primary",
        key="bars",
    )

    latency = LineChart(
        series=[
            ChartSeries(
                points=[920.0, 880.0, 860.0, 845.0, 830.0],
                label="latency ms",
                color_scheme="secondary",
            )
        ],
        width=480.0,
        height=160.0,
        key="line",
    )

    table = DataTable(
        columns=["Class", "Conf"],
        rows=[["banana", "84%"], ["apple", "41%"], ["pear", "18%"]],
        key="table",
    )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16.0)),
        key="root",
        children=[
            _section("DETECTION OVERLAY (boxes)", key="s-ov", body=overlay),
            _section("BAR CHART (per-class confidence)", key="s-bar", body=conf_bars),
            _section("LINE CHART (latency trend)", key="s-line", body=latency),
            _section("CONFIDENCE BADGES", key="s-cb", body=badges),
            _section("DATA TABLE", key="s-tbl", body=table),
            _section("METRIC CARDS", key="s-m", body=metrics),
        ],
    )


def main() -> None:
    """Run the dashboard in the Qt simulator (lazy import keeps the module clean)."""
    from tempestroid.renderers.qt import run_qt

    run_qt(view, make_state())


if __name__ == "__main__":
    main()
