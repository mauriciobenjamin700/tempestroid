"""Conformance suite (phase D): pin the two ``Style`` translators against each
other so they cannot silently diverge.

Two checks:

* **Golden snapshots** — for a set of canonical styles, capture the combined
  output of *both* translators (``Style → Compose`` spec + ``Style → Qt`` QSS and
  alignment) and compare against committed golden files. Any change to either
  translator that alters the output breaks the golden, forcing a conscious review.
  Regenerate with ``UPDATE_GOLDEN=1 pytest tests/conformance``.

* **Coverage parity** — for every ``Style`` field, assert which translators react
  to it matches a documented table. If a translator starts or stops handling a
  field, this fails until the table (and the divergence rationale) is updated.

Qt needs a (headless) PySide6 import; ``tests/conftest.py`` forces the offscreen
platform.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tempestroid import to_compose
from tempestroid.renderers.qt.style_translator import layout_alignment, to_qss
from tempestroid.style import (
    AlignItems,
    Border,
    Color,
    Corners,
    Curve,
    Edge,
    FlexDirection,
    FontStyle,
    FontWeight,
    Gradient,
    GradientDirection,
    GradientStop,
    JustifyContent,
    Position,
    Shadow,
    SideBorder,
    StackAlign,
    Style,
    TextAlign,
    TextDecoration,
    TextOverflow,
    Transition,
)

_GOLDEN_DIR = Path(__file__).parent / "golden"


def _align(style: Style, *, is_row: bool) -> int | None:
    """Serialize the Qt alignment flag for a style as a stable int (or None)."""
    flag = layout_alignment(is_row=is_row, justify=style.justify, align=style.align)
    return int(flag) if flag is not None else None


def snapshot(style: Style) -> dict[str, Any]:
    """Capture both translators' output for ``style`` as a JSON-able dict.

    Args:
        style: The style to translate.

    Returns:
        ``{"compose": ..., "qt": {...}}`` — the combined conformance snapshot.
    """
    return {
        "compose": to_compose(style),
        "qt": {
            "qss_leaf": to_qss(style, with_padding=True),
            "qss_container": to_qss(style, with_padding=False),
            "align_row": _align(style, is_row=True),
            "align_col": _align(style, is_row=False),
        },
    }


# --- canonical cases (golden-pinned) ---------------------------------------

CASES: dict[str, Style] = {
    "empty": Style(),
    "paint": Style(
        background=Color(r=10, g=20, b=30), color=Color(r=200, g=210, b=220)
    ),
    "box": Style(
        padding=Edge.all(8),
        border=Border(width=2, color=Color(r=0, g=0, b=0)),
        radius=6,
    ),
    "typography": Style(
        font_family="Roboto", font_size=18, font_weight=FontWeight.BOLD,
        text_align=TextAlign.CENTER,
    ),
    "flex_row_center": Style(
        direction=FlexDirection.ROW,
        justify=JustifyContent.CENTER,
        align=AlignItems.CENTER,
        gap=12,
    ),
    "flex_col_end": Style(
        direction=FlexDirection.COLUMN,
        justify=JustifyContent.END,
        align=AlignItems.END,
    ),
    "sizing": Style(
        width=120, height=48, min_width=40, max_width=320,
        min_height=20, max_height=80,
    ),
    "grow_margin": Style(grow=1, margin=Edge.all(16)),
    "animated": Style(
        background=Color(r=10, g=20, b=30),
        transition=Transition(duration_ms=300, curve=Curve.EASE_IN_OUT, delay_ms=50),
    ),
    "effects": Style(
        opacity=0.5,
        shadow=Shadow(
            color=Color(r=0, g=0, b=0, a=0.4), blur=8, offset_x=0, offset_y=2
        ),
    ),
    "gradient": Style(
        background=Gradient(
            direction=GradientDirection.LEFT_RIGHT,
            stops=[
                GradientStop(color=Color(r=255, g=0, b=0), position=0.0),
                GradientStop(color=Color(r=0, g=0, b=255), position=1.0),
            ],
        ),
    ),
    "corners_sides": Style(
        radius=Corners(top_left=12, top_right=12, bottom_right=0, bottom_left=0),
        border=SideBorder(bottom=Border(width=1, color=Color(r=200, g=200, b=200))),
    ),
    "rich_text": Style(
        font_style=FontStyle.ITALIC,
        text_decoration=TextDecoration.UNDERLINE,
        letter_spacing=1.5,
        line_height=1.4,
        max_lines=2,
        text_overflow=TextOverflow.ELLIPSIS,
    ),
    "align_self_aspect": Style(align_self=AlignItems.CENTER, aspect_ratio=1.5),
    "stack_align": Style(stack_align=StackAlign.BOTTOM_END),
    "absolute_insets": Style(
        position=Position.ABSOLUTE, top=0, right=8, bottom=4, left=0
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_snapshot(name: str) -> None:
    """Each canonical style matches its committed golden snapshot."""
    snap = snapshot(CASES[name])
    path = _GOLDEN_DIR / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", "utf-8")
    assert path.exists(), f"missing golden for {name!r}; run UPDATE_GOLDEN=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert snap == expected, (
        f"conformance drift for {name!r}; review and re-run UPDATE_GOLDEN=1 if intended"
    )


# --- coverage parity --------------------------------------------------------

#: One representative non-default value per ``Style`` field.
_SAMPLES: dict[str, Any] = {
    "direction": FlexDirection.ROW,
    "justify": JustifyContent.CENTER,
    "align": AlignItems.CENTER,
    "align_self": AlignItems.CENTER,
    "grow": 1.0,
    "gap": 8.0,
    "padding": Edge.all(4),
    "margin": Edge.all(4),
    "border": Border(width=1.0, color=Color(r=0, g=0, b=0)),
    "radius": 4.0,
    "background": Color(r=1, g=2, b=3),
    "color": Color(r=1, g=2, b=3),
    "opacity": 0.5,
    "shadow": Shadow(color=Color(r=0, g=0, b=0), blur=4.0, offset_y=2.0),
    "font_family": "Arial",
    "font_size": 12.0,
    "font_weight": FontWeight.BOLD,
    "font_style": FontStyle.ITALIC,
    "text_align": TextAlign.CENTER,
    "text_decoration": TextDecoration.UNDERLINE,
    "letter_spacing": 1.5,
    "line_height": 1.4,
    "max_lines": 2,
    "text_overflow": TextOverflow.ELLIPSIS,
    "width": 100.0,
    "height": 100.0,
    "min_width": 10.0,
    "max_width": 200.0,
    "min_height": 10.0,
    "max_height": 200.0,
    "aspect_ratio": 1.5,
    "transition": Transition(duration_ms=300),
    "stack_align": StackAlign.CENTER,
    "position": Position.ABSOLUTE,
    "top": 4.0,
    "right": 4.0,
    "bottom": 4.0,
    "left": 4.0,
}

#: Expected ``field -> (compose_reacts, qt_reacts)``. Divergences (compose-only)
#: are intentional and documented:
#:   grow/gap   — Qt applies these on the QBoxLayout (stretch/spacing), not the
#:                Style translator (see A3 notes), so the translator doesn't react.
#:   margin     — not wired on the Qt side yet (post-v1).
#:   text_align — Qt would express this via a widget property, not QSS (post-v1).
#:   width/height (fixed) — Qt fixed-size not wired yet (A3 notes).
#:   direction  — structural (picks Row vs Column at the widget); neither
#:                translator emits it into QSS/spec.
#:   transition — Compose maps it to ``animate*AsState``; Qt animation is
#:                renderer-imperative (QPropertyAnimation), not a QSS property, so
#:                the ``Style → Qt`` translator does not react to it (A3 notes).
#:   align_self — Qt applies it per-child via ``QBoxLayout.setAlignment`` in the
#:                renderer (like grow), not through the Style translator.
#:   opacity/shadow — Qt applies these as a ``QGraphicsEffect`` in the renderer,
#:                not via QSS, so the translator doesn't react.
#:   letter_spacing — no QSS property; Qt applies it via ``QFont`` in the renderer.
#:   line_height/max_lines/text_overflow — Qt realizes these in the custom
#:                ``_TextLabel`` (``QTextLayout`` leading + line cap + elide), not
#:                via QSS.
#:   aspect_ratio — Compose ``Modifier.aspectRatio``; Qt derives the missing fixed
#:                dimension in the renderer (no QSS equivalent).
#:   margin — emitted as a QSS box-model rule by both translators, so Qt reacts.
#:   stack_align/position/top/right/bottom/left — stacking/overlay placement.
#:                Compose lowers them into the spec (``Box`` alignment / inset
#:                padding); Qt realizes them imperatively as ``QWidget`` geometry
#:                in the ``_StackWidget`` (no QSS property), so the ``Style → Qt``
#:                translator does not react.
_COVERAGE: dict[str, tuple[bool, bool]] = {
    "direction": (False, False),
    "justify": (True, True),
    "align": (True, True),
    "align_self": (True, False),
    "grow": (True, False),
    "gap": (True, False),
    "padding": (True, True),
    "margin": (True, False),
    "border": (True, True),
    "radius": (True, True),
    "background": (True, True),
    "color": (True, True),
    "opacity": (True, False),
    "shadow": (True, False),
    "font_family": (True, True),
    "font_size": (True, True),
    "font_weight": (True, True),
    "font_style": (True, True),
    "text_align": (True, False),
    "text_decoration": (True, True),
    "letter_spacing": (True, False),
    "line_height": (True, False),
    "max_lines": (True, False),
    "text_overflow": (True, False),
    "width": (True, False),
    "height": (True, False),
    "min_width": (True, True),
    "max_width": (True, True),
    "min_height": (True, True),
    "max_height": (True, True),
    "aspect_ratio": (True, False),
    "transition": (True, False),
    "stack_align": (True, False),
    "position": (True, False),
    "top": (True, False),
    "right": (True, False),
    "bottom": (True, False),
    "left": (True, False),
}


def test_coverage_table_covers_every_field() -> None:
    """The coverage/sample tables list exactly the Style fields (no drift)."""
    fields = set(Style.model_fields)
    assert set(_SAMPLES) == fields
    assert set(_COVERAGE) == fields


@pytest.mark.parametrize("field", sorted(_SAMPLES))
def test_coverage_parity(field: str) -> None:
    """Which translators react to a field matches the documented table."""
    base = snapshot(Style())
    snap = snapshot(Style(**{field: _SAMPLES[field]}))
    compose_reacts = snap["compose"] != base["compose"]
    qt_reacts = snap["qt"] != base["qt"]
    assert (compose_reacts, qt_reacts) == _COVERAGE[field], (
        f"{field!r} coverage changed to (compose={compose_reacts}, qt={qt_reacts}); "
        f"update _COVERAGE + its rationale if this divergence is intended"
    )
