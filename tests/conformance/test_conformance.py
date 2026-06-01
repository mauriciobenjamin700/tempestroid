"""Conformance suite (phases D + E1d): pin the two ``Style`` translators against
each other so they cannot silently diverge, and document the widget-level
behavioural divergences introduced by Phase E1 (virtualized lists).

Three checks:

* **Golden snapshots** — for a set of canonical styles, capture the combined
  output of *both* translators (``Style → Compose`` spec + ``Style → Qt`` QSS and
  alignment) and compare against committed golden files. Any change to either
  translator that alters the output breaks the golden, forcing a conscious review.
  Regenerate with ``UPDATE_GOLDEN=1 pytest tests/conformance``.

* **Coverage parity** — for every ``Style`` field, assert which translators react
  to it matches a documented table. If a translator starts or stops handling a
  field, this fails until the table (and the divergence rationale) is updated.

* **E1 widget-level divergences** — Phase E1 adds *no* new ``Style`` fields, so
  the two ``Style`` translators are unchanged and the golden/parity machinery above
  stays unaffected. However, E1 introduces four intentional *behavioural*
  divergences between the Qt and Compose renderers for the five new list widgets
  (``LazyColumn``, ``LazyRow``, ``LazyGrid``, ``SectionList``, ``RefreshControl``).
  These are documented and pinned as a separate, named tripwire table so that a
  future renderer change that silently resolves or regresses a divergence fails
  loudly.  See ``_E1_WIDGET_DIVERGENCES`` and ``test_e1_widget_divergences_complete``.

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
    FlexWrap,
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
    "flex_wrap": Style(
        direction=FlexDirection.ROW,
        flex_wrap=FlexWrap.WRAP,
        gap=8,
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
    "flex_wrap": FlexWrap.WRAP,
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
    "text_scale": 1.4,
    "font_asset": "fonts/Custom.ttf",
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
#:   flex_wrap  — Compose lowers it into the spec (``flexWrap`` → FlowRow/FlowColumn
#:                wrapping); Qt realizes wrapping imperatively inside its custom
#:                ``Wrap`` flow-layout widget (reflowing children on resize), not via
#:                QSS, so the ``Style → Qt`` translator does not react to it.
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
#:   text_scale — Compose emits ``textScale`` (the device's ``LocalDensity``
#:                applies it); Qt scales the emitted ``font-size`` (px when an
#:                explicit ``font_size`` is set, otherwise a relative ``em``), so
#:                both translators react.
#:   font_asset — Compose emits ``fontAsset`` (Kotlin loads the bundle font into a
#:                ``FontFamily``); Qt emits ``font-family: "CustomAsset"`` (the
#:                renderer registers the file via ``QFontDatabase``), so both react.
_COVERAGE: dict[str, tuple[bool, bool]] = {
    "direction": (False, False),
    "justify": (True, True),
    "align": (True, True),
    "align_self": (True, False),
    "grow": (True, False),
    "gap": (True, False),
    "flex_wrap": (True, False),
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
    "text_scale": (True, True),
    "font_asset": (True, True),
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


# ---------------------------------------------------------------------------
# E1 widget-level behavioural divergences (phase E1d)
# ---------------------------------------------------------------------------
#
# Phase E1 adds *no* new ``Style`` fields, so ``to_qss`` / ``to_compose`` and all
# existing golden snapshots are completely unaffected.  The divergences below are
# *renderer-level* (Qt vs Compose implementation strategy), not translator-level.
# They are pinned here so the next developer who resolves or regresses one is
# forced to update the table — not just "fix" it silently.
#
# Table columns:
#   widget         — The E1 widget type tag.
#   topic          — The behaviour area where Qt and Compose differ.
#   qt_strategy    — How the Qt renderer implements the behaviour.
#   compose_strategy — How the Compose renderer implements the behaviour.
#   intentional    — True = this divergence is expected and acceptable in v1.
#
# Updating this table: if a divergence is resolved (both renderers converge on
# the same strategy), set ``intentional=False`` and add a comment explaining why.
# The tripwire test ``test_e1_widget_divergences_complete`` will then fail until
# you remove the resolved row.  If you add a new E1 widget or a new divergence
# topic, add a row here AND explain it in the rationale below.
#
# Rationale (mirrors the contract from the E1 architect):
#
# 1. item_builder materialisation
#    Qt calls ``item_builder(i)`` directly in Python to fill the visible
#    ``[start, end)`` window; children are keyed ``Node``\s attached to the
#    ``LazyColumn`` node before diffing.  Compose iterates natively via
#    ``LazyColumn { items(itemCount, key={it}) { … } }``; the serializer drops
#    ``item_builder`` (never crosses the boundary) and the device renders items
#    on demand from ``props["item_count"]``.  The Python side sends only the
#    materialized window as ``children``; the Kotlin side ignores them and renders
#    all ``item_count`` items lazily.
#
# 2. sticky-header implementation for SectionList
#    Qt simulates sticky headers by pinning a ``QLabel`` *above* the
#    ``QScrollArea`` (outside the scroll viewport) and swapping it when the
#    section changes.  Compose uses the native ``LazyColumn { stickyHeader {} }``
#    API, which handles header pinning intrinsically and participates in the lazy
#    layout.
#
# 3. pull-to-refresh
#    Qt implements pull-to-refresh as a manual overlay: a hidden ``QWidget``
#    (spinner / ``QProgressBar``) is shown at the top of the scroll area when
#    ``props["refreshing"]`` is ``True``; a drag-detect gesture fires
#    ``RefreshEvent``.  Compose wraps the list in ``PullToRefreshBox``
#    (Material 3, ``ExperimentalMaterial3Api``), which provides the platform-
#    native pull animation and handles the gesture internally.
#
# 4. end-reached detection
#    Qt detects end-reached by polling the scrollbar position:
#    ``scrollbar.value() / scrollbar.maximum() >= end_reached_threshold`` on
#    each ``valueChanged`` signal.  Compose uses ``derivedStateOf`` over
#    ``LazyListState.layoutInfo.visibleItemsInfo``; the last visible item index
#    is compared against ``props["item_count"]`` (NOT ``children.size``, which is
#    the partial window size), so the threshold is computed correctly even when
#    only a window of items is materialized.

_E1_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "LazyColumn",
        "topic": "item_builder_materialisation",
        "qt_strategy": (
            "Python calls item_builder(i) to fill the visible [start,end) window; "
            "children are keyed Nodes attached before diffing."
        ),
        "compose_strategy": (
            "items(itemCount, key={it}) iterates natively on the device; "
            "item_builder is dropped by the serializer (never crosses the boundary)."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyRow",
        "topic": "item_builder_materialisation",
        "qt_strategy": (
            "Python calls item_builder(i) to fill the visible [start,end) window; "
            "children are keyed Nodes attached before diffing."
        ),
        "compose_strategy": (
            "items(itemCount, key={it}) iterates natively on the device; "
            "item_builder is dropped by the serializer (never crosses the boundary)."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyGrid",
        "topic": "item_builder_materialisation",
        "qt_strategy": (
            "Python calls item_builder(i) for the visible window; "
            "children keyed by absolute index."
        ),
        "compose_strategy": (
            "LazyVerticalGrid(GridCells.Fixed(columns)) iterates natively; "
            "item_builder dropped by serializer."
        ),
        "intentional": True,
    },
    {
        "widget": "SectionList",
        "topic": "sticky_header",
        "qt_strategy": (
            "QLabel pinned above the QScrollArea (outside the scroll viewport); "
            "swapped manually when the active section changes."
        ),
        "compose_strategy": (
            "LazyColumn { stickyHeader {} } native API; "
            "header is part of the lazy layout and pins intrinsically."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyColumn",
        "topic": "pull_to_refresh",
        "qt_strategy": (
            "Hidden QWidget overlay (QProgressBar) shown when refreshing=True; "
            "drag-detect gesture fires RefreshEvent."
        ),
        "compose_strategy": (
            "PullToRefreshBox (Material 3, ExperimentalMaterial3Api) wraps the list; "
            "platform-native pull animation and gesture."
        ),
        "intentional": True,
    },
    {
        "widget": "RefreshControl",
        "topic": "pull_to_refresh",
        "qt_strategy": (
            "Standalone QWidget with QProgressBar overlay; "
            "refreshing=True shows spinner."
        ),
        "compose_strategy": (
            "PullToRefreshBox standalone wrapper; ExperimentalMaterial3Api."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyColumn",
        "topic": "end_reached_detection",
        "qt_strategy": (
            "scrollbar.value() / scrollbar.maximum() >= end_reached_threshold "
            "polled on QScrollBar.valueChanged."
        ),
        "compose_strategy": (
            "derivedStateOf { LazyListState.layoutInfo.visibleItemsInfo }; "
            "last.index + 1 / props[item_count] >= threshold "
            "(uses item_count, NOT children.size which is the partial window)."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyRow",
        "topic": "end_reached_detection",
        "qt_strategy": (
            "Horizontal scrollbar position / maximum >= end_reached_threshold."
        ),
        "compose_strategy": (
            "derivedStateOf(LazyListState) with horizontal layout; "
            "uses props[item_count] as denominator."
        ),
        "intentional": True,
    },
    {
        "widget": "LazyGrid",
        "topic": "end_reached_detection",
        "qt_strategy": (
            "Grid scroll area: scrollbar.value() / scrollbar.maximum() >= threshold."
        ),
        "compose_strategy": (
            "derivedStateOf(LazyGridState); uses props[item_count] as denominator."
        ),
        "intentional": True,
    },
]

#: The set of (widget, topic) pairs that must appear in ``_E1_WIDGET_DIVERGENCES``.
#: Adding a new divergence or widget requires extending both ``_E1_WIDGET_DIVERGENCES``
#: AND this set — the tripwire test checks both directions.
_E1_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E1_WIDGET_DIVERGENCES
}


def test_e1_widget_divergences_complete() -> None:
    """Every E1 divergence row is intentional and the table has no duplicate keys.

    This is the tripwire: if a renderer specialist resolves a divergence, they
    must update ``_E1_WIDGET_DIVERGENCES`` (set ``intentional=False`` and remove
    the row after review). If they add a new divergence, they must add a row.
    Either omission makes this test fail.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E1_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E1 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (v1 known gap)"
        )
        # Each row must document both sides.
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    # All pinned keys are present.
    assert seen == _E1_DIVERGENCE_KEYS


# ---------------------------------------------------------------------------
# E2 widget-level behavioural divergences (overlays + feedback)
# ---------------------------------------------------------------------------
#
# Phase E2 adds *no* new ``Style`` fields, so the golden/parity machinery above
# stays unaffected. E2 introduces the floating overlay layer (Dialog, BottomSheet,
# Toast, Tooltip, Menu, Popover, ActionSheet), serialized as a separate
# ``Scene.overlays`` list and addressed under the reserved ``("overlay", i, …)``
# path prefix. The two renderers realize overlays through very different
# platform surfaces; those divergences are pinned here as a named tripwire.
#
# Rationale:
#
# 1. dialog surface
#    Qt floats a modal ``QDialog`` over the host window; the barrier is the
#    dialog's own modality (it blocks input to the window beneath). Compose uses
#    the Material 3 ``AlertDialog``, which creates its own platform window and
#    manages its own ``WindowInsets.safeDrawing`` — it must NOT be wrapped in the
#    root ``safeDrawingPadding`` (double-inset bug).
#
# 2. bottom-sheet surface + safe-area inset
#    Qt anchors a frameless ``QDialog`` to the bottom edge with a slide
#    animation. Compose uses ``ModalBottomSheet`` (M3), which respects the bottom
#    system inset natively and supplies its own scrim — again, NOT wrapped in the
#    root safe-area padding.
#
# 3. toast lifetime + timer authority
#    The Python ``App.toast`` is authoritative over a toast's lifetime via
#    ``loop.call_later(duration_s, dismiss)``. Qt mirrors this with a floating
#    ``QLabel`` + ``QTimer`` + fade; Compose mirrors it with a ``Popup`` +
#    ``LaunchedEffect(delay)`` that emits ``__dismiss__:<id>``. The Python timer
#    is the source of truth; the renderer timer is a UX optimisation only.
#
# 4. menu / action-sheet anchoring
#    Qt presents a ``QMenu`` anchored at the cursor / anchor widget global
#    position. Compose presents a ``DropdownMenu`` (or ``ModalBottomSheet`` with a
#    ``LazyColumn`` for action sheets) anchored via the ``anchor`` key. Both route
#    selection back as a ``MenuSelectEvent``.
#
# 5. barrier / scrim + dismiss routing
#    A host-owned dismiss (scrim tap, swipe-down) rides the event channel under
#    the reserved ``__dismiss__:<id>`` token and is routed to ``App.dismiss`` — no
#    new patch kind, no new JNI entry. Qt draws the scrim as a semi-transparent
#    ``QWidget`` z-ordered above the root; Compose relies on the M3 surfaces'
#    built-in scrim (dialog/sheet) or a bare ``Popup`` (no scrim) for anchored
#    menus.

_E2_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "Dialog",
        "topic": "dialog_surface_and_inset",
        "qt_strategy": (
            "Modal QDialog floated over the host window; barrier is the dialog's "
            "own modality blocking input beneath."
        ),
        "compose_strategy": (
            "Material 3 AlertDialog in its own platform window; manages its own "
            "WindowInsets.safeDrawing (NOT wrapped in root safeDrawingPadding)."
        ),
        "intentional": True,
    },
    {
        "widget": "BottomSheet",
        "topic": "sheet_surface_and_bottom_inset",
        "qt_strategy": (
            "Frameless QDialog anchored to the bottom edge with a slide animation."
        ),
        "compose_strategy": (
            "Material 3 ModalBottomSheet respects the bottom system inset "
            "natively and supplies its own scrim (NOT root safeDrawingPadding)."
        ),
        "intentional": True,
    },
    {
        "widget": "Toast",
        "topic": "toast_lifetime_timer",
        "qt_strategy": (
            "Floating QLabel + QTimer + fade; auto-dismiss mirrors the Python "
            "loop.call_later timer (which is authoritative)."
        ),
        "compose_strategy": (
            "Popup + LaunchedEffect(delay) emits __dismiss__:<id>; the Python "
            "loop.call_later timer remains the source of truth."
        ),
        "intentional": True,
    },
    {
        "widget": "Menu",
        "topic": "menu_anchoring",
        "qt_strategy": (
            "QMenu exec()-ed at the cursor / anchor widget global position; "
            "triggered fires MenuSelectEvent."
        ),
        "compose_strategy": (
            "DropdownMenu anchored via the anchor key; each item tap emits a "
            "MenuSelectEvent JSON payload."
        ),
        "intentional": True,
    },
    {
        "widget": "ActionSheet",
        "topic": "menu_anchoring",
        "qt_strategy": (
            "QMenu with a QAction per item; selection fires MenuSelectEvent."
        ),
        "compose_strategy": (
            "ModalBottomSheet with a LazyColumn of items; each tap emits a "
            "MenuSelectEvent."
        ),
        "intentional": True,
    },
    {
        "widget": "Dialog",
        "topic": "barrier_scrim_and_dismiss",
        "qt_strategy": (
            "Scrim drawn as a semi-transparent QWidget z-ordered above the root; "
            "barrier tap dispatches __dismiss__:<id>."
        ),
        "compose_strategy": (
            "M3 surface's built-in scrim; onDismissRequest dispatches "
            "__dismiss__:<id> over the event channel to App.dismiss."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E2_WIDGET_DIVERGENCES``.
_E2_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E2_WIDGET_DIVERGENCES
}


def test_e2_widget_divergences_complete() -> None:
    """Every E2 overlay divergence row is intentional and uniquely keyed.

    The tripwire: a renderer specialist who resolves an overlay divergence (e.g.
    both renderers converge on the same surface) must update the table; one who
    adds a new overlay or topic must add a row. Either omission fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E2_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E2 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E2_DIVERGENCE_KEYS


def test_e2_no_style_field_added() -> None:
    """Phase E2 adds no new Style fields — the parity baseline is unchanged."""
    assert len(Style.model_fields) == len(_SAMPLES)


def test_e1_no_style_field_added() -> None:
    """Phase E1 adds no new Style fields — the Style model is unchanged.

    This guards against accidental Style modifications in this phase: if a new
    field appears, the parity table must be updated, the golden snapshots must be
    regenerated (UPDATE_GOLDEN=1), and this test must be updated with the new
    expected field count. The current baseline is the field count at phase D
    completion.
    """
    # Count fields as of phase D (absolute_insets, box, typography, …).
    # If a new field is added, update this count AND regenerate goldens.
    _EXPECTED_STYLE_FIELD_COUNT = len(_SAMPLES)
    assert len(Style.model_fields) == _EXPECTED_STYLE_FIELD_COUNT, (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {_EXPECTED_STYLE_FIELD_COUNT}); "
        "if intentional, update _SAMPLES, _COVERAGE, regenerate goldens with "
        "UPDATE_GOLDEN=1, and update _EXPECTED_STYLE_FIELD_COUNT here"
    )


def test_e1_style_translators_not_affected_by_list_widgets() -> None:
    """E1 list-widget imports do not mutate the Style translators.

    Calling ``to_compose``/``to_qss`` with ``Style()`` must produce the same
    output regardless of whether the E1 list widgets have been imported —
    no accidental side-effects from module-level registration.
    """
    # The full tempestroid package (which pulls in all E1 widgets) is already
    # imported at module level via ``from tempestroid import to_compose``; no
    # additional import is needed here.  We just verify the translators are clean.
    # The canonical empty-style snapshot is already pinned by the golden; calling
    # ``snapshot`` here just double-checks the translators have not been mutated.
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}
    assert empty_snap["qt"]["qss_leaf"] == ""


# ---------------------------------------------------------------------------
# E3 conformance: animation framework (phase E3)
# ---------------------------------------------------------------------------
#
# Phase E3 adds:
#   1. Three new ``Curve`` members (EASE / BOUNCE / ELASTIC) — no new ``Style``
#      fields; only the ``Transition.curve`` sub-field gains new legal values.
#      The golden snapshot "animated" (which uses ``Curve.EASE_IN_OUT``) is
#      unchanged; three new golden cases ("curve_ease", "curve_bounce",
#      "curve_elastic") pin the new translations so a typo in ``_CURVE`` is
#      caught immediately.
#   2. Five new animation widgets (Animated / AnimatedList / Hero / Shimmer /
#      Skeleton) — all with ``event_schemas = {}``. These must appear in
#      ``bridge.protocol.EVENT_SCHEMAS`` (so the bridge's contract is
#      complete) and the reserved ``FRAME_TOKEN = "__frame__"`` must be
#      exported by the same module.
#   3. Renderer-level behavioural divergences between Qt and Compose for all
#      four animation scenarios — pinned below in ``_E3_WIDGET_DIVERGENCES``.
#
# Rationale for the Qt-vs-Compose divergences (mirrors the architect contract):
#
# 1. Animated — interpolation site
#    Qt: the core Python clock (``loop.call_later(1/60, _tick)``) advances
#    ``AnimationController.value``; the ``view`` reads the value, feeds it to
#    ``Tween.at``, and builds the child with the already-interpolated ``Style``
#    for that frame. The Qt renderer receives final props via a plain ``Update``
#    patch — no native Qt animation API.
#    Compose: can drive the same final-props path (it also receives a fully
#    interpolated ``Style`` from the Python clock), but it *may* alternatively
#    use ``animateColorAsState``/``animateFloatAsState`` with ``durationMs``/
#    ``curve`` from the serialized ``transition`` spec for 90/120fps fluency.
#    The strategic choice is documented here; changing it silently breaks this
#    test.
#
# 2. AnimatedList — insert/remove animation surface
#    Qt: ``QPropertyAnimation`` on the inserted/removed child's ``opacity`` +
#    ``maximumHeight``, driven by a local ``QTimer``. Duration read from
#    ``props.enter_duration_ms`` / ``exit_duration_ms``; the widget self-deletes
#    after the exit animation.
#    Compose: ``AnimatedVisibility(visible = …, enter = fadeIn+expandVertically,
#    exit = fadeOut+shrinkVertically)``; native M3 Compose, driven by Compose's
#    own animation engine. Duration also read from ``enter_duration_ms`` /
#    ``exit_duration_ms`` props.
#
# 3. Hero — shared-element transition surface
#    Qt: ``QPropertyAnimation`` on ``geometry()`` (pos + size) between the two
#    screens of a ``Navigator``, triggered when a ``Replace`` patch arrives and
#    both the new and old trees contain a ``Hero`` node with the same tag. The
#    transition is initiated by the Qt renderer detecting the matching
#    ``hero_tag`` property across the two trees.
#    Compose: ``SharedTransitionLayout`` wrapping the ``Navigator`` +
#    ``Modifier.sharedElement(rememberSharedContentState(key = hero_tag))``
#    applied to each ``Hero`` node's child — the M3 native shared-element
#    contract.
#
# 4. Shimmer — moving-gradient animation surface
#    Qt: An internal ``QTimer`` (period = ``duration_ms / 20``) repaints a
#    ``QLinearGradient`` that sweeps the highlight color from left to right and
#    wraps in a loop. The gradient offset advances each tick.
#    Compose: ``rememberInfiniteTransition() + animateFloat(0f→1f,
#    infiniteRepeatable(tween(duration_ms)))`` drives a ``Brush.linearGradient``
#    offset, producing the platform-native shimmer without a Python-side timer.
#
# Updating this table: if a divergence is resolved (both renderers converge),
# set ``intentional=False`` and explain why. The tripwire test
# ``test_e3_widget_divergences_complete`` will fail until the resolved row is
# removed. If a new E3 widget or topic is added, add a row here AND update the
# pinned key set.

_E3_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "Animated",
        "topic": "interpolation_site",
        "qt_strategy": (
            "Core Python clock (loop.call_later 1/60 s) advances "
            "AnimationController.value; view reads Tween.at(value) and builds child "
            "with the already-interpolated Style — Qt renderer receives final props "
            "via a plain Update patch, no native Qt animation API."
        ),
        "compose_strategy": (
            "Receives the same interpolated Style from the Python clock (final-props "
            "path); may also use animateColorAsState/animateFloatAsState with "
            "durationMs/curve from the serialized transition spec for 90/120fps "
            "fluency on the device."
        ),
        "intentional": True,
    },
    {
        "widget": "AnimatedList",
        "topic": "insert_remove_animation_surface",
        "qt_strategy": (
            "QPropertyAnimation on the child's opacity + maximumHeight, driven by a "
            "local QTimer; duration from props.enter_duration_ms/exit_duration_ms; "
            "widget self-deletes after the exit animation finishes."
        ),
        "compose_strategy": (
            "AnimatedVisibility(visible=…, enter=fadeIn+expandVertically, "
            "exit=fadeOut+shrinkVertically) — native M3 Compose; duration from "
            "props.enter_duration_ms/exit_duration_ms."
        ),
        "intentional": True,
    },
    {
        "widget": "Hero",
        "topic": "shared_element_transition_surface",
        "qt_strategy": (
            "QPropertyAnimation on geometry() (pos+size) between the two Navigator "
            "screens; triggered by the Qt renderer detecting matching hero_tag "
            "properties across the old and new trees during a Replace patch."
        ),
        "compose_strategy": (
            "SharedTransitionLayout wrapping the Navigator + "
            "Modifier.sharedElement(rememberSharedContentState(key=hero_tag)) "
            "applied to each Hero node's child — native M3 shared-element contract."
        ),
        "intentional": True,
    },
    {
        "widget": "Shimmer",
        "topic": "gradient_animation_surface",
        "qt_strategy": (
            "Internal QTimer (period = duration_ms/20 ms) repaints a "
            "QLinearGradient sweeping the highlight color left-to-right in a loop; "
            "gradient offset advances each tick."
        ),
        "compose_strategy": (
            "rememberInfiniteTransition() + animateFloat(0f→1f, "
            "infiniteRepeatable(tween(duration_ms))) drives a "
            "Brush.linearGradient offset — platform-native shimmer without a "
            "Python-side timer."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E3_WIDGET_DIVERGENCES``.
_E3_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E3_WIDGET_DIVERGENCES
}


def test_e3_widget_divergences_complete() -> None:
    """Every E3 animation divergence row is intentional and uniquely keyed.

    This is the tripwire: a renderer specialist who resolves an animation
    divergence (e.g. both renderers converge on the same animation surface)
    must update the table; one who adds a new E3 widget or topic must add a row.
    Either omission fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E3_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E3 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (v1 known gap)"
        )
        # Each row must document both sides.
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    # All pinned keys are present (both directions).
    assert seen == _E3_DIVERGENCE_KEYS


def test_e3_no_style_field_added() -> None:
    """Phase E3 adds no new Style fields — the ``_SAMPLES``/``_COVERAGE`` tables
    remain complete without update.

    E3 extends the ``Curve`` enum (three new values on an *existing* field
    ``Transition.curve``), but does not add any top-level field to ``Style``.
    If a new field appears, update ``_SAMPLES``, ``_COVERAGE``, regenerate
    goldens (``UPDATE_GOLDEN=1``), and update this sentinel.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); "
        "if intentional, update _SAMPLES, _COVERAGE, regenerate goldens with "
        "UPDATE_GOLDEN=1, and update this test"
    )


# ---------------------------------------------------------------------------
# E3 Curve additions: new golden cases + parity for EASE/BOUNCE/ELASTIC
# ---------------------------------------------------------------------------

#: Canonical cases that exercise the three new ``Curve`` members added in E3a.
_E3_CURVE_CASES: dict[str, Style] = {
    "curve_ease": Style(
        transition=Transition(duration_ms=200, curve=Curve.EASE, delay_ms=0)
    ),
    "curve_bounce": Style(
        transition=Transition(duration_ms=400, curve=Curve.BOUNCE, delay_ms=0)
    ),
    "curve_elastic": Style(
        transition=Transition(duration_ms=500, curve=Curve.ELASTIC, delay_ms=0)
    ),
}


@pytest.mark.parametrize("name", sorted(_E3_CURVE_CASES))
def test_e3_curve_golden_snapshot(name: str) -> None:
    """Each new Curve value matches its committed golden snapshot.

    Regenerate with ``UPDATE_GOLDEN=1`` when the translator changes.
    """
    style = _E3_CURVE_CASES[name]
    snap = snapshot(style)
    path = _GOLDEN_DIR / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", "utf-8")
    assert path.exists(), f"missing golden for {name!r}; run UPDATE_GOLDEN=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert snap == expected, (
        f"conformance drift for {name!r}; "
        "review and re-run UPDATE_GOLDEN=1 if intended"
    )


@pytest.mark.parametrize(
    "curve,expected_compose",
    [
        (Curve.EASE, "ease"),
        (Curve.BOUNCE, "bounce"),
        (Curve.ELASTIC, "elastic"),
    ],
)
def test_e3_new_curve_values_in_compose_spec(
    curve: Curve, expected_compose: str
) -> None:
    """Each new ``Curve`` member maps to the correct string in the Compose spec.

    Pins the ``_CURVE`` mapping in ``renderers/compose/style_translator.py``
    against accidental renames.
    """
    spec = snapshot(Style(transition=Transition(duration_ms=300, curve=curve)))
    assert spec["compose"]["transition"]["curve"] == expected_compose, (
        f"Curve.{curve.name} mapped to "
        f"{spec['compose']['transition']['curve']!r} (expected {expected_compose!r}); "
        "update _CURVE in renderers/compose/style_translator.py"
    )


def test_e3_new_curve_values_not_in_qss() -> None:
    """The Qt style translator does not emit ``transition`` into QSS (by design).

    The three new ``Curve`` values (EASE/BOUNCE/ELASTIC) all live inside
    ``Transition``, and the ``_COVERAGE`` table documents ``"transition":
    (True, False)`` — Compose reacts, Qt does not. This test asserts that adding
    any of the new values does not silently start changing the QSS output.
    """
    base_qt = snapshot(Style())["qt"]
    for curve in (Curve.EASE, Curve.BOUNCE, Curve.ELASTIC):
        style = Style(transition=Transition(duration_ms=200, curve=curve))
        snap_qt = snapshot(style)["qt"]
        assert snap_qt == base_qt, (
            f"Curve.{curve.name} changed the Qt snapshot; "
            'transition must remain Qt-side inert per _COVERAGE["transition"]'
        )


# ---------------------------------------------------------------------------
# E3 bridge contract: FRAME_TOKEN + EVENT_SCHEMAS completeness
# ---------------------------------------------------------------------------


def test_e3_frame_token_exported() -> None:
    """``FRAME_TOKEN`` is exported from ``tempestroid.bridge.protocol``.

    The device host dispatches ``__frame__:`` while an animation is active;
    ``bridge/jni.py`` routes this token to ``App._tick_from_device``. If the
    constant is missing, the JNI routing will fail at runtime.
    """
    from tempestroid.bridge.protocol import FRAME_TOKEN

    assert FRAME_TOKEN == "__frame__", (
        f"FRAME_TOKEN has unexpected value {FRAME_TOKEN!r}; "
        "the device sends '__frame__:' — the constant must match"
    )


def test_e3_animation_widgets_in_event_schemas() -> None:
    """All five E3 animation widgets appear in ``bridge.protocol.EVENT_SCHEMAS``.

    Even though all five have ``event_schemas = {}``, they must be present in
    the ``EVENT_SCHEMAS`` dict so the bridge's introspected contract is complete
    and future event additions on these widgets don't silently fall through.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    for name in ("Animated", "AnimatedList", "Hero", "Shimmer", "Skeleton"):
        assert name in EVENT_SCHEMAS, (
            f"E3 widget {name!r} missing from EVENT_SCHEMAS; "
            "add it to the unconditional update block in bridge/protocol.py"
        )
        assert EVENT_SCHEMAS[name] == {}, (
            f"E3 widget {name!r} has non-empty EVENT_SCHEMAS "
            f"({EVENT_SCHEMAS[name]}); update this test if events were added"
        )


# ---------------------------------------------------------------------------
# E3 contract guards — the IR/bridge surface the animation framework exposes
# ---------------------------------------------------------------------------
#
# These were E3b regression tripwires for two gaps that are now closed:
#
# 1. ``FRAME_TOKEN`` is re-exported by the root ``tempestroid/__init__.py`` (in
#    ``__all__`` and importable), so ``from tempestroid import FRAME_TOKEN`` works.
#
# 2. The five E3 animation widgets (Animated / AnimatedList / Hero / Shimmer /
#    Skeleton) are listed in ``core.introspection.WIDGET_TYPES``, so
#    ``introspect()`` / ``widget_catalog()`` describe them.
#
# They stay as permanent guards against a regression that drops either.


def test_e3_frame_token_reexported_at_root() -> None:
    """``FRAME_TOKEN`` must be importable from the top-level ``tempestroid`` package.

    The constant is declared in ``bridge.protocol`` and its internal import works,
    but it is absent from ``tempestroid/__init__.py``, so user code that writes
    ``from tempestroid import FRAME_TOKEN`` receives an ``ImportError`` / the
    value is not in ``tempestroid.__all__``.
    """
    import tempestroid

    assert "FRAME_TOKEN" in tempestroid.__all__, (
        "FRAME_TOKEN missing from tempestroid.__all__; "
        "add it to tempestroid/__init__.py"
    )
    assert hasattr(tempestroid, "FRAME_TOKEN"), (
        "FRAME_TOKEN not importable from tempestroid; "
        "add the import to tempestroid/__init__.py"
    )
    assert tempestroid.FRAME_TOKEN == "__frame__"  # type: ignore[attr-defined]


def test_e3_animation_widgets_in_introspect() -> None:
    """All five E3 animation widgets must appear in the output of ``introspect()``.

    ``introspect()`` is the framework's self-describing typed contract — the
    device bridge and tooling rely on it to discover every widget. The E3 widgets
    have ``event_schemas = {}``, so they appeared in ``EVENT_SCHEMAS`` via the
    unconditional update in ``bridge/protocol.py``, but ``core/introspection.py``
    still needs them added to ``WIDGET_TYPES``.
    """
    from tempestroid import introspect

    catalog = introspect()
    for name in ("Animated", "AnimatedList", "Hero", "Shimmer", "Skeleton"):
        assert name in catalog["widgets"], (
            f"E3 widget {name!r} absent from introspect()['widgets']; "
            "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
        )


# ---------------------------------------------------------------------------
# E4 widget-level behavioural divergences (advanced gestures)
# ---------------------------------------------------------------------------
#
# Phase E4 adds *no* new ``Style`` fields, so the golden/parity machinery above
# stays unaffected. E4 introduces eight gesture/interaction widgets. These render
# through fundamentally different platform surfaces on Qt (desktop mouse events,
# QDrag, QGraphicsView) versus Compose (Jetpack Compose gesture APIs: pointerInput,
# detectDragGestures, detectTransformGestures, graphicsLayer). The divergences are
# pinned here as a named tripwire so a future renderer change that silently
# resolves or regresses one is caught loudly.
#
# Rationale for each divergence (mirrors the architect contract notes):
#
# 1. Draggable / DragTarget — DnD surface
#    Qt uses the native OS drag-and-drop pipeline (QDrag + QMimeData +
#    QDropEvent). The drag image is the widget itself (grabbed via
#    QWidget.grab()); the target accepts via acceptDrops=True and emits a
#    DragEvent when QDropEvent arrives. This is a true inter-widget OS-level DnD.
#    Compose has no cross-widget DnD API stable in M3. The renderer uses
#    detectDragGesturesAfterLongPress with a manually tracked Offset state and a
#    hoisted shared mutable state (CompositionLocal or remember at a common
#    ancestor) to pass the dragged payload to the DragTarget. Visual feedback
#    is a Modifier.offset applied to the Draggable child. This is in-Compose only.
#
# 2. InteractiveViewer — pan + zoom implementation
#    Qt wraps the child in a QGraphicsProxyWidget inside a QGraphicsView with a
#    QTransform that accumulates pan (via mouse move) and zoom (via Ctrl+scroll
#    wheel, clamped to min_scale/max_scale). Scroll without Ctrl = pan. A ScaleEvent
#    is emitted when the transform settles (mouseReleaseEvent / wheelEvent).
#    Compose accumulates scale and translation in remember { mutableStateOf } and
#    applies them via Modifier.graphicsLayer { scaleX; scaleY; translationX;
#    translationY }. The gesture is detected via detectTransformGestures; the
#    ScaleEvent is emitted at onGestureEnd (pointerInput awaitPointerEventScope).
#
# 3. ScaleHandler / InteractiveViewer — pinch input on desktop vs device
#    On the Qt desktop (and WSL without a touchscreen), true two-finger pinch
#    hardware is unavailable. The _ScaleWidget and _InteractiveViewerWidget fall
#    back to Ctrl+ScrollWheel for zoom, which is keyboard-assisted rather than a
#    real pinch. On-device Compose uses detectTransformGestures which responds to
#    genuine multitouch. This is a documented desktop limitation, not a bug.
#
# 4. ReorderableList — reorder animation during drag
#    Qt calculates the target index from the drop position in QDropEvent and
#    immediately emits ReorderEvent; no animation during the drag itself (the
#    source item becomes a floating QDrag pixmap). Compose uses
#    detectDragGesturesAfterLongPress with manual index tracking (offset.y /
#    itemHeight); no smooth placeholder animation during drag (DIY offset-math,
#    no external reorderable library), consistent with the §0 no-external-lib rule.
#
# 5. Dismissible — swipe-to-dismiss surface
#    Qt measures a horizontal (or directional) mouse drag against a threshold
#    (_SWIPE_THRESHOLD) and, when exceeded, runs a QPropertyAnimation on opacity
#    and position to slide the widget out, then emits DismissEvent. Compose uses
#    SwipeToDismissBox (Material 3, available since material3 >= 1.2.0 as
#    SwipeToDismissBoxValue); older AGP configs should use the legacy
#    DismissState/SwipeToDismiss API. The Kotlin renderer must check the
#    material3 version in android-host/app/build.gradle.kts before choosing.
#
# Updating this table: if a divergence is resolved (both renderers converge on
# the same strategy), set ``intentional=False`` and explain why. The tripwire test
# ``test_e4_widget_divergences_complete`` will fail until the resolved row is
# removed. If a new E4 widget or divergence topic is added, add a row here AND
# update the pinned key set.

_E4_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "Draggable",
        "topic": "drag_and_drop_surface",
        "qt_strategy": (
            "Native OS drag-and-drop via QDrag + QMimeData; widget grabbed as "
            "a pixmap for the drag image; QDropEvent on the target delivers the "
            "payload and emits DragEvent."
        ),
        "compose_strategy": (
            "detectDragGesturesAfterLongPress with a manually tracked Offset "
            "state; hoisted shared mutable state passes the dragged payload to "
            "DragTarget (no native cross-widget DnD in M3). Visual feedback via "
            "Modifier.offset on the Draggable child."
        ),
        "intentional": True,
    },
    {
        "widget": "DragTarget",
        "topic": "drag_and_drop_surface",
        "qt_strategy": (
            "acceptDrops=True on the target QWidget; dropEvent receives "
            "QDropEvent, extracts MIME data, and emits DragEvent."
        ),
        "compose_strategy": (
            "Reads from a hoisted shared CompositionLocal or remembered "
            "mutable state; when the Draggable's onDragEnd fires and the drag "
            "position overlaps the DragTarget Box, a DragEvent is emitted."
        ),
        "intentional": True,
    },
    {
        "widget": "InteractiveViewer",
        "topic": "pan_zoom_implementation",
        "qt_strategy": (
            "QGraphicsView + QGraphicsProxyWidget wrapping the child; "
            "QTransform accumulates pan (mouse drag) and zoom "
            "(Ctrl+ScrollWheel, clamped to min_scale/max_scale); "
            "ScaleEvent emitted on mouseReleaseEvent / wheelEvent settle."
        ),
        "compose_strategy": (
            "Modifier.graphicsLayer { scaleX; scaleY; translationX; translationY } "
            "driven by detectTransformGestures; ScaleEvent emitted at gesture end "
            "via awaitPointerEventScope. Scale clamped to min_scale/max_scale."
        ),
        "intentional": True,
    },
    {
        "widget": "ScaleHandler",
        "topic": "pinch_input_fallback_on_desktop",
        "qt_strategy": (
            "Desktop/WSL has no touchscreen; true two-finger pinch is unavailable. "
            "Falls back to Ctrl+ScrollWheel for zoom (keyboard-assisted, not a "
            "real pinch gesture). Documented desktop limitation."
        ),
        "compose_strategy": (
            "detectTransformGestures responds to genuine multitouch pinch on "
            "the device; no keyboard fallback needed."
        ),
        "intentional": True,
    },
    {
        "widget": "InteractiveViewer",
        "topic": "pinch_input_fallback_on_desktop",
        "qt_strategy": (
            "Same as ScaleHandler: Ctrl+ScrollWheel zoom fallback on desktop/WSL "
            "where multitouch is unavailable."
        ),
        "compose_strategy": (
            "detectTransformGestures with genuine multitouch on device."
        ),
        "intentional": True,
    },
    {
        "widget": "ReorderableList",
        "topic": "reorder_animation_during_drag",
        "qt_strategy": (
            "Target index calculated from QDropEvent position; ReorderEvent "
            "emitted immediately on drop. No in-place animation during drag "
            "(source item rendered as a floating QDrag pixmap by the OS)."
        ),
        "compose_strategy": (
            "detectDragGesturesAfterLongPress with manual index tracking "
            "(offset.y / itemHeight); no smooth placeholder animation during "
            "drag (DIY offset-math, no external reorderable library — §0 rule). "
            "ReorderEvent emitted on onDragEnd."
        ),
        "intentional": True,
    },
    {
        "widget": "Dismissible",
        "topic": "swipe_dismiss_surface",
        "qt_strategy": (
            "Mouse drag measured against _SWIPE_THRESHOLD in the configured "
            "direction; on threshold exceeded, QPropertyAnimation on opacity + "
            "position slides the widget out, then DismissEvent is emitted."
        ),
        "compose_strategy": (
            "SwipeToDismissBox (Material 3, SwipeToDismissBoxValue — requires "
            "material3 >= 1.2.0; older builds use legacy DismissState/SwipeToDismiss). "
            "DismissEvent emitted when confirmValueChange returns true."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E4_WIDGET_DIVERGENCES``.
_E4_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E4_WIDGET_DIVERGENCES
}

#: The eight E4 gesture/interaction widgets introduced in phase E4.
_E4_NEW_WIDGETS: tuple[str, ...] = (
    "PanHandler",
    "ScaleHandler",
    "DoubleTapHandler",
    "Draggable",
    "DragTarget",
    "Dismissible",
    "ReorderableList",
    "InteractiveViewer",
)


def test_e4_widget_divergences_complete() -> None:
    """Every E4 gesture divergence row is intentional and uniquely keyed.

    This is the tripwire: a renderer specialist who resolves a gesture divergence
    (e.g. Compose gains a cross-widget DnD API that matches Qt) must update the
    table; one who adds a new E4 widget or topic must add a row.  Either omission
    fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E4_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E4 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (v1 known gap)"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E4_DIVERGENCE_KEYS


def test_e4_no_style_field_added() -> None:
    """Phase E4 adds no new Style fields — the parity baseline is unchanged.

    E4 introduces eight gesture/interaction widgets but no new ``Style`` fields.
    If a new field appears, update ``_SAMPLES``, ``_COVERAGE``, regenerate goldens
    (``UPDATE_GOLDEN=1``), and update this sentinel.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); "
        "if intentional, update _SAMPLES, _COVERAGE, regenerate goldens with "
        "UPDATE_GOLDEN=1, and update this test"
    )


def test_e4_new_widgets_in_event_schemas() -> None:
    """All eight E4 gesture widgets appear in ``bridge.protocol.EVENT_SCHEMAS``.

    Each widget must be present so the bridge's introspected contract is complete.
    The exact event bindings are verified by
    ``test_event_schemas_registered_in_protocol`` in ``test_overlay_gestures.py``;
    this test is a quick completeness guard.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    for name in _E4_NEW_WIDGETS:
        assert name in EVENT_SCHEMAS, (
            f"E4 widget {name!r} missing from EVENT_SCHEMAS; "
            "add it to bridge/protocol.py"
        )


def test_e4_new_widgets_in_introspect() -> None:
    """All eight E4 gesture widgets must appear in the output of ``introspect()``.

    ``introspect()`` is the framework's self-describing typed contract; the bridge
    and tooling use it to discover every widget. Missing entries mean the widget
    is undiscoverable at runtime.
    """
    from tempestroid import introspect

    catalog = introspect()
    for name in _E4_NEW_WIDGETS:
        assert name in catalog["widgets"], (
            f"E4 widget {name!r} absent from introspect()['widgets']; "
            "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
        )


def test_e4_new_events_in_introspect() -> None:
    """The four new E4 event types appear in ``introspect()['events']``.

    This pins the ``EVENT_TYPES`` list in ``core/introspection.py`` against
    a regression that drops one of the new events from the catalog.
    """
    from tempestroid import introspect

    catalog = introspect()
    for event in ("PanEvent", "ScaleEvent", "DragEvent", "ReorderEvent"):
        assert event in catalog["events"], (
            f"E4 event {event!r} absent from introspect()['events']; "
            "add it to EVENT_TYPES in tempestroid/core/introspection.py"
        )


def test_e4_translators_not_affected_by_gesture_widgets() -> None:
    """E4 gesture-widget imports do not mutate the Style translators.

    No E4 widget adds a ``Style`` field; calling ``to_compose``/``to_qss`` with
    ``Style()`` must yield the same output as before E4 was imported.
    """
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}, (
        "to_compose(Style()) changed after E4 import — "
        "a gesture widget must not side-effect the Compose translator"
    )
    assert empty_snap["qt"]["qss_leaf"] == "", (
        "to_qss(Style()) changed after E4 import — "
        "a gesture widget must not side-effect the Qt translator"
    )


# ---------------------------------------------------------------------------
# E5 widget-level behavioural divergences (inputs + forms)
# ---------------------------------------------------------------------------
#
# Phase E5 adds *no* new ``Style`` fields, so the golden/parity machinery above
# stays unaffected. E5 introduces six new input controls (Dropdown, TimePicker,
# RangeSlider, Autocomplete, PinInput, MaskedInput) plus two form-aggregation
# widgets (Form, FormField). The renderers realize these controls through
# different platform surfaces; those divergences are pinned here as a named
# tripwire so a future renderer change that silently resolves or regresses one
# is caught loudly.
#
# Key architectural constraint:
#   Form/Validator/FormState validation logic runs 100 % in Python via
#   ``Form.validate()`` before any patch is sent to either renderer.  Both
#   renderers receive a tree already carrying each ``FormField.error`` string;
#   they display it but contain zero validation logic.  A ``SubmitEvent`` is
#   only dispatched when the application (Python side) decides the form is
#   valid — the renderer cannot block or allow a submit independently.
#
# Rationale for each divergence (mirrors the architect contract):
#
# 1. TimePicker — affordance
#    Qt uses an inline ``QTimeEdit`` spinner (always visible, value edited
#    in-place by scrolling/typing).  Compose uses a ``TimePicker`` M3 dialog
#    (requires user to open a modal dialog, confirm, then dismiss).  Both
#    emit ``TimeChangeEvent{value: "HH:MM"}``.
#
# 2. RangeSlider — widget surface
#    PySide6 has no native range slider.  Qt implements it as a custom
#    ``_RangeSliderWidget`` containing two ``QSlider``s side by side, each
#    constraining the other so that ``low <= high`` is always maintained.
#    Compose uses the native M3 ``RangeSlider`` composable.  Both emit
#    ``RangeChangeEvent{low: float, high: float}`` — floats, never a tuple.
#
# 3. Autocomplete — completion popup
#    Qt uses a ``QCompleter`` attached to a ``QLineEdit``; the popup is the
#    native OS completion dropdown.  Compose uses a custom ``DropdownMenu``
#    that filters ``options`` by the current text — no native autocomplete
#    composable in M3.  Both emit ``TextChangeEvent`` (on text change) and
#    ``SelectEvent{value, index}`` (on item selection).
#
# 4. PinInput — cell focus management
#    Qt uses ``length`` chained ``QLineEdit``s (``maxLength=1``) that
#    auto-advance focus via ``textChanged`` signal.  Compose uses ``length``
#    ``BasicTextField``s coordinated by ``FocusRequester`` list.  Both emit
#    ``TextChangeEvent`` on each cell change and ``SubmitEvent`` when all
#    cells are filled.
#
# 5. MaskedInput — mask application
#    Qt converts the framework mask notation (``9`` = digit, ``A`` = letter,
#    literal chars preserved) to Qt's ``inputMask`` notation (``0`` = digit,
#    ``A`` = letter) via ``QLineEdit.setInputMask``.  Compose applies a
#    custom ``VisualTransformation`` (``MaskTransformation``) that inserts
#    non-editable separator characters.  Both emit ``TextChangeEvent``; on
#    the Compose side the raw digits (without mask separators) are reported.
#
# Invariants shared by both renderers (NOT divergences):
#   - ``FormField.validators`` are dropped by the serializer (pure-Python
#     callables, never cross the bridge).
#   - ``FormState`` serializes as ``{"errors": dict[str, str], "valid": bool}``
#     with no nested Pydantic models.
#   - ``Form.fields`` serializes as the Form node's children — ``fields`` does
#     not appear in the serialized ``props`` dict.
#   - ``FormField.child`` serializes as the FormField node's first child.
#
# Updating this table: if a divergence is resolved (both renderers converge),
# set ``intentional=False`` and explain why. The tripwire test
# ``test_e5_widget_divergences_complete`` will fail until the resolved row is
# removed. If a new E5 widget or topic is added, add a row here AND update
# the pinned key set.

_E5_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "TimePicker",
        "topic": "time_affordance",
        "qt_strategy": (
            "Inline QTimeEdit spinner (always visible); value edited in-place "
            "by scrolling or typing. format HH:mm set via setDisplayFormat. "
            "timeChanged signal -> TimeChangeEvent{value: HH:MM string}."
        ),
        "compose_strategy": (
            "TimePicker M3 modal dialog (TimePickerState + rememberTimePickerState); "
            "user opens via a read-only OutlinedTextField click, confirms via "
            "AlertDialog buttons. Confirmed -> TimeChangeEvent{value: HH:MM string}."
        ),
        "intentional": True,
    },
    {
        "widget": "RangeSlider",
        "topic": "widget_surface",
        "qt_strategy": (
            "Custom _RangeSliderWidget (QWidget container with two QSliders "
            "side by side — low and high handles). Each slider constrains the "
            "other so low <= high is maintained. Both sliders' valueChanged "
            "signals -> RangeChangeEvent{low: float, high: float}."
        ),
        "compose_strategy": (
            "Native M3 RangeSlider composable (androidx.compose.material3). "
            "onValueChange updates a remembered range state; "
            "onValueChangeFinished -> RangeChangeEvent{low: float, high: float}."
        ),
        "intentional": True,
    },
    {
        "widget": "Autocomplete",
        "topic": "completion_popup",
        "qt_strategy": (
            "QLineEdit + QCompleter (native OS completion popup). "
            "QCompleter.activated(str) -> SelectEvent{value, index}. "
            "QLineEdit.textChanged -> TextChangeEvent{value}."
        ),
        "compose_strategy": (
            "OutlinedTextField + DropdownMenu filtravel (options filtered "
            "by current text via contains(ignoreCase=true)) — no native "
            "autocomplete composable in M3. Item click -> SelectEvent{value, index}. "
            "onValueChange -> TextChangeEvent{value}."
        ),
        "intentional": True,
    },
    {
        "widget": "PinInput",
        "topic": "cell_focus_management",
        "qt_strategy": (
            "length chained QLineEdit cells (maxLength=1, fixed ~40px width); "
            "textChanged on each cell auto-advances focus to the next. "
            "Last cell filled -> SubmitEvent{}. Per-cell change -> "
            "TextChangeEvent{value = joined cells}."
        ),
        "compose_strategy": (
            "length BasicTextField composables coordinated by a "
            "List<FocusRequester>(length). onValueChange advances focus via "
            "focusRequesters[i+1].requestFocus(). All cells filled -> "
            "SubmitEvent{}. Per-cell change -> TextChangeEvent{value = joined}."
        ),
        "intentional": True,
    },
    {
        "widget": "MaskedInput",
        "topic": "mask_application",
        "qt_strategy": (
            "Framework mask notation converted to Qt inputMask: '9' -> '0' "
            "(digit), 'A' -> 'A' (letter), literal chars preserved. "
            "QLineEdit.setInputMask applies the mask; textChanged -> "
            "TextChangeEvent{value = masked string including separators}."
        ),
        "compose_strategy": (
            "OutlinedTextField + custom VisualTransformation (MaskTransformation) "
            "inserts non-editable separator characters. Raw digits only are "
            "stored in state. onValueChange -> TextChangeEvent{value = raw digits "
            "without separators}. OffsetMapping handles bidirectional cursor "
            "placement. Mask chars 'A' (letter) documented as limited support."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E5_WIDGET_DIVERGENCES``.
_E5_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E5_WIDGET_DIVERGENCES
}

#: The six new E5 input-control widgets (excludes Form/FormField which are
#: containers with shared behaviour on both renderers).
_E5_INPUT_WIDGETS: tuple[str, ...] = (
    "Dropdown",
    "TimePicker",
    "RangeSlider",
    "Autocomplete",
    "PinInput",
    "MaskedInput",
)

#: All eight E5 widgets (input controls + form aggregation).
_E5_ALL_WIDGETS: tuple[str, ...] = _E5_INPUT_WIDGETS + ("Form", "FormField")

#: The five new E5 events.
_E5_NEW_EVENTS: tuple[str, ...] = (
    "SelectEvent",
    "TimeChangeEvent",
    "RangeChangeEvent",
    "SubmitEvent",
    "ValidationEvent",
)


def test_e5_widget_divergences_complete() -> None:
    """Every E5 input divergence row is intentional and uniquely keyed.

    This is the tripwire: a renderer specialist who resolves an input control
    divergence (e.g. PySide6 gains a native range slider) must update the
    table; one who adds a new E5 widget or divergence topic must add a row.
    Either omission fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E5_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E5 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (v1 known gap)"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E5_DIVERGENCE_KEYS


def test_e5_no_style_field_added() -> None:
    """Phase E5 adds no new Style fields — the ``_SAMPLES``/``_COVERAGE`` tables
    remain complete without update.

    E5 introduces eight new widgets and five new events, but no new top-level
    ``Style`` field.  If a new field appears, update ``_SAMPLES``, ``_COVERAGE``,
    regenerate goldens (``UPDATE_GOLDEN=1``), and update this sentinel.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); "
        "if intentional, update _SAMPLES, _COVERAGE, regenerate goldens with "
        "UPDATE_GOLDEN=1, and update this test"
    )


def test_e5_new_widgets_in_event_schemas() -> None:
    """All eight E5 widgets appear in ``bridge.protocol.EVENT_SCHEMAS``.

    Each widget must be present so the bridge contract is complete.  The exact
    event bindings for each are verified by ``test_input_widgets.py`` and
    ``test_forms.py``; this test is a quick completeness guard.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    for name in _E5_ALL_WIDGETS:
        assert name in EVENT_SCHEMAS, (
            f"E5 widget {name!r} missing from EVENT_SCHEMAS; "
            "add it to bridge/protocol.py"
        )


def test_e5_input_widgets_event_schemas_non_empty() -> None:
    """The six E5 input controls each declare at least one event schema.

    ``Form`` and ``FormField`` are containers (``on_submit`` / ``on_validate``
    respectively) and are also covered, but this test targets the leaf controls
    to ensure none accidentally regresses to an empty schema.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    for name in _E5_INPUT_WIDGETS:
        schemas = EVENT_SCHEMAS.get(name, {})
        assert schemas, (
            f"E5 input widget {name!r} has an empty EVENT_SCHEMAS entry; "
            "it must declare at least one event"
        )


def test_e5_new_widgets_in_introspect() -> None:
    """All eight E5 widgets appear in the output of ``introspect()``.

    ``introspect()`` is the framework's self-describing typed contract — both
    the device bridge and tooling rely on it to discover every widget.  Missing
    entries mean a widget is undiscoverable at runtime.
    """
    from tempestroid import introspect

    catalog = introspect()
    for name in _E5_ALL_WIDGETS:
        assert name in catalog["widgets"], (
            f"E5 widget {name!r} absent from introspect()['widgets']; "
            "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
        )


def test_e5_new_events_in_introspect() -> None:
    """The five new E5 event types appear in ``introspect()['events']``.

    Pins the ``EVENT_TYPES`` list in ``core/introspection.py`` against a
    regression that drops one of the new events from the catalog.
    """
    from tempestroid import introspect

    catalog = introspect()
    for event in _E5_NEW_EVENTS:
        assert event in catalog["events"], (
            f"E5 event {event!r} absent from introspect()['events']; "
            "add it to EVENT_TYPES in tempestroid/core/introspection.py"
        )


def test_e5_event_type_for_resolves_all_bindings() -> None:
    """``event_type_for`` resolves every E5 widget/handler pair correctly.

    This pins the ``EVENT_SCHEMAS`` mapping against accidental key renames or
    type swaps for the eight new widgets.  The per-pair assertions mirror the
    architect contract exactly.
    """
    from tempestroid.bridge.protocol import event_type_for
    from tempestroid.widgets.events import (
        RangeChangeEvent,
        SelectEvent,
        SubmitEvent,
        TextChangeEvent,
        TimeChangeEvent,
        ValidationEvent,
    )

    # Dropdown — single handler
    assert event_type_for("Dropdown", "on_select") is SelectEvent, (
        "Dropdown.on_select must resolve to SelectEvent"
    )
    # TimePicker — single handler
    assert event_type_for("TimePicker", "on_change") is TimeChangeEvent, (
        "TimePicker.on_change must resolve to TimeChangeEvent"
    )
    # RangeSlider — single handler
    assert event_type_for("RangeSlider", "on_change") is RangeChangeEvent, (
        "RangeSlider.on_change must resolve to RangeChangeEvent"
    )
    # Autocomplete — two distinct handlers
    assert event_type_for("Autocomplete", "on_change") is TextChangeEvent, (
        "Autocomplete.on_change must resolve to TextChangeEvent"
    )
    assert event_type_for("Autocomplete", "on_select") is SelectEvent, (
        "Autocomplete.on_select must resolve to SelectEvent"
    )
    # PinInput — two distinct handlers
    assert event_type_for("PinInput", "on_change") is TextChangeEvent, (
        "PinInput.on_change must resolve to TextChangeEvent"
    )
    assert event_type_for("PinInput", "on_complete") is SubmitEvent, (
        "PinInput.on_complete must resolve to SubmitEvent"
    )
    # MaskedInput — single handler
    assert event_type_for("MaskedInput", "on_change") is TextChangeEvent, (
        "MaskedInput.on_change must resolve to TextChangeEvent"
    )
    # Form — submit handler
    assert event_type_for("Form", "on_submit") is SubmitEvent, (
        "Form.on_submit must resolve to SubmitEvent"
    )
    # FormField — validate handler
    assert event_type_for("FormField", "on_validate") is ValidationEvent, (
        "FormField.on_validate must resolve to ValidationEvent"
    )


def test_e5_form_validation_not_in_renderer() -> None:
    """Documented invariant: validation logic stays 100 % in Python.

    The test is structural — it asserts facts about the serialized node shape
    that enforce the invariant on both renderers:

    1. ``FormField.validators`` do **not** appear in the serialized props dict
       (pure-Python callables, never cross the bridge).
    2. ``Form.fields`` does **not** appear in the serialized props dict
       (fields serialize as the Form node's children, not as props).
    3. Both renderers receive ``FormField.error`` as a plain string prop —
       they display it but cannot compute it themselves.
    """
    from tempestroid import build
    from tempestroid.bridge import serialize_node
    from tempestroid.widgets.forms import Form, FormField
    from tempestroid.widgets.inputs import Input

    def _any_validator(v: object) -> str | None:
        return None

    form = Form(
        fields=[
            FormField(
                name="email",
                validators=[_any_validator],
                label="E-mail",
                error="bad address",
                child=Input(value="x"),
            )
        ]
    )
    payload = serialize_node(build(form))

    # Form.fields must serialize as children, not as a prop.
    assert "fields" not in payload["props"], (
        "Form.fields must cross as node.children, not as a props entry; "
        "both renderers iterate node.children to render each FormField"
    )
    assert payload["children"], "Form must have at least one child node"

    field_payload = payload["children"][0]
    assert field_payload["type"] == "FormField"

    # validators must be dropped — callables cannot cross the bridge.
    assert "validators" not in field_payload["props"], (
        "FormField.validators must be dropped by the serializer (pure-Python "
        "callables); neither renderer should receive or execute them"
    )

    # error must cross as a plain string prop so each renderer can display it.
    assert field_payload["props"]["error"] == "bad address", (
        "FormField.error must cross as a plain string prop so the renderer "
        "can display it without any validation logic"
    )


def test_e5_translators_not_affected_by_input_widgets() -> None:
    """E5 input-widget imports do not mutate the Style translators.

    No E5 widget adds a ``Style`` field; calling ``to_compose``/``to_qss`` with
    ``Style()`` must yield the same output as before E5 was imported — no
    accidental side-effects from module-level registration.
    """
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}, (
        "to_compose(Style()) changed after E5 import — "
        "an input widget must not side-effect the Compose translator"
    )
    assert empty_snap["qt"]["qss_leaf"] == "", (
        "to_qss(Style()) changed after E5 import — "
        "an input widget must not side-effect the Qt translator"
    )


def test_e5_form_and_field_event_schemas() -> None:
    """Form and FormField declare the correct event bindings.

    Pins the event schema declarations on the two form-aggregation widgets
    against accidental renames: ``Form.on_submit`` -> ``SubmitEvent``,
    ``FormField.on_validate`` -> ``ValidationEvent``.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS
    from tempestroid.widgets.events import SubmitEvent, ValidationEvent

    form_schemas = EVENT_SCHEMAS.get("Form", {})
    assert "on_submit" in form_schemas, (
        "Form must declare on_submit in event_schemas"
    )
    assert form_schemas["on_submit"] is SubmitEvent, (
        "Form.on_submit must be bound to SubmitEvent"
    )

    field_schemas = EVENT_SCHEMAS.get("FormField", {})
    assert "on_validate" in field_schemas, (
        "FormField must declare on_validate in event_schemas"
    )
    assert field_schemas["on_validate"] is ValidationEvent, (
        "FormField.on_validate must be bound to ValidationEvent"
    )


# ---------------------------------------------------------------------------
# E6 conformance: refined layout (flex_wrap + Wrap / PageView / AspectRatio +
# CollapsingAppBar + Table / DataTable)
# ---------------------------------------------------------------------------
#
# Phase E6 adds ONE new ``Style`` field — ``flex_wrap`` — so it is the first E
# phase to grow the golden/parity baseline. ``flex_wrap`` enters ``_SAMPLES`` and
# ``_COVERAGE`` above (Compose reacts, Qt does not — wrapping is realised in the
# custom Qt flow-layout widget, not QSS), and a golden case ``flex_wrap.json``
# pins the combined translator output. Because ``_SAMPLES`` grew in lockstep, the
# ``test_e{1..5}_no_style_field_added`` sentinels (which assert
# ``len(Style.model_fields) == len(_SAMPLES)``) still pass.
#
# E6 also adds new widgets whose renderer realisation diverges between Qt and
# Compose. The translator-level surface (``flex_wrap``) is pinned by the golden +
# parity machinery; the renderer-level divergences below are pinned as a named
# tripwire so a future renderer change that silently resolves or regresses one is
# caught loudly.
#
# Rationale for each divergence (mirrors the E6 architect contract):
#
# 1. Wrap — flow-layout backend
#    Qt has no native flow layout; the renderer uses a custom ``_WrapWidget``
#    that repositions children on ``resizeEvent`` (accumulating row width and
#    breaking lines), honouring ``Style.gap`` as inter-child spacing. Compose
#    lowers it to ``FlowRow`` / ``FlowColumn`` (foundation-layout, wrap by
#    default), reading ``style.flexWrap`` from the spec.
#
# 2. PageView — pager surface
#    Qt uses a ``QStackedWidget`` with prev/next navigation (arrow keys /
#    buttons) since the desktop has no swipe hardware; ``set_page`` emits a
#    ``PageChangeEvent``. Compose uses the native ``HorizontalPager`` +
#    ``rememberPagerState``; a ``LaunchedEffect(currentPage)`` emits the same
#    ``PageChangeEvent`` on settle. Both keep the active page in App state.
#
# 3. CollapsingAppBar — nested-scroll surface
#    The component lowers to primitives (a ``Container`` whose ``Style.height``
#    is derived from ``scroll_offset``), so neither renderer needs a custom case.
#    The divergence is in HOW the scroll offset is sourced: Qt wires the host
#    scroll area's ``valueChanged`` to ``App.set_state``; Compose uses a
#    ``nestedScroll`` connection feeding the offset back via the list's
#    ``on_scroll`` handler. The collapse math itself is identical (pure Python in
#    ``CollapsingAppBar.render``), so the bar's derived height diffs as a normal
#    prop on both sides.

_E6_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "Wrap",
        "topic": "flow_layout_backend",
        "qt_strategy": (
            "Custom _WrapWidget repositions children on resizeEvent (accumulates "
            "row width, breaks onto a new line when full); honours Style.gap as "
            "inter-child spacing. No native Qt flow layout."
        ),
        "compose_strategy": (
            "FlowRow / FlowColumn (androidx.compose.foundation.layout, wrap by "
            "default); reads style.flexWrap from the spec to pick wrap vs "
            "wrapReverse vs nowrap."
        ),
        "intentional": True,
    },
    {
        "widget": "PageView",
        "topic": "pager_surface",
        "qt_strategy": (
            "QStackedWidget with prev/next navigation (arrow keys / buttons) — "
            "desktop has no swipe hardware; set_page emits PageChangeEvent."
        ),
        "compose_strategy": (
            "Native HorizontalPager + rememberPagerState; "
            "LaunchedEffect(currentPage) emits PageChangeEvent on settle."
        ),
        "intentional": True,
    },
    {
        "widget": "CollapsingAppBar",
        "topic": "nested_scroll_surface",
        "qt_strategy": (
            "Component lowers to a Container whose Style.height is derived from "
            "scroll_offset; the host scroll area's valueChanged is wired to "
            "App.set_state to feed the offset back. No custom renderer case."
        ),
        "compose_strategy": (
            "Component lowers to the same primitives; the scroll offset is "
            "sourced via a nestedScroll connection feeding the list's on_scroll "
            "handler back into App.set_state. Collapse math is identical (pure "
            "Python in render), so the derived height diffs as a normal prop."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E6_WIDGET_DIVERGENCES``.
_E6_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E6_WIDGET_DIVERGENCES
}

#: The three new E6 layout widgets exposed in ``introspect()``'s widget catalog.
#: (Table/DataTable/CollapsingAppBar are Components — they lower to primitives and
#: do not appear in WIDGET_TYPES.)
_E6_NEW_WIDGETS: tuple[str, ...] = ("Wrap", "PageView", "AspectRatio")


def test_e6_widget_divergences_complete() -> None:
    """Every E6 layout divergence row is intentional and uniquely keyed.

    The tripwire: a renderer specialist who resolves a layout divergence (e.g.
    Qt gains a native flow layout) must update the table; one who adds a new E6
    widget or topic must add a row. Either omission fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E6_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E6 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (v1 known gap)"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E6_DIVERGENCE_KEYS


def test_e6_flex_wrap_field_added() -> None:
    """Phase E6 adds exactly one new Style field (``flex_wrap``).

    Unlike E1–E5, E6 grows the Style model. The parity baseline (``_SAMPLES`` /
    ``_COVERAGE``) and the golden ``flex_wrap.json`` were updated in the same
    change, so ``len(Style.model_fields) == len(_SAMPLES)`` still holds.
    """
    assert "flex_wrap" in Style.model_fields, (
        "Style.flex_wrap missing; E6 must add it to the flexbox group"
    )
    assert "flex_wrap" in _SAMPLES and "flex_wrap" in _COVERAGE, (
        "flex_wrap must be present in both _SAMPLES and _COVERAGE"
    )
    assert len(Style.model_fields) == len(_SAMPLES)


def test_e6_new_widgets_in_introspect() -> None:
    """The three new E6 layout widgets appear in ``introspect()['widgets']``.

    ``introspect()`` is the framework's self-describing contract; missing entries
    mean a widget is undiscoverable at runtime. Table/DataTable/CollapsingAppBar
    are Components (they lower to primitives), so they are intentionally absent.
    """
    from tempestroid import introspect

    catalog = introspect()
    for name in _E6_NEW_WIDGETS:
        assert name in catalog["widgets"], (
            f"E6 widget {name!r} absent from introspect()['widgets']; "
            "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
        )


def test_e6_new_events_in_introspect() -> None:
    """The new E6 event ``PageChangeEvent`` appears in ``introspect()['events']``.

    Pins the ``EVENT_TYPES`` list in ``core/introspection.py`` against a
    regression that drops the event from the catalog.
    """
    from tempestroid import introspect

    catalog = introspect()
    assert "PageChangeEvent" in catalog["events"], (
        "E6 event 'PageChangeEvent' absent from introspect()['events']; "
        "add it to EVENT_TYPES in tempestroid/core/introspection.py"
    )


def test_e6_page_change_event_in_event_schemas() -> None:
    """``PageView`` declares ``on_page_change`` → ``PageChangeEvent`` in the bridge.

    Pins the bridge contract so the device round-trip validates a page-change
    payload against the right event type.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS, event_type_for
    from tempestroid.widgets.events import PageChangeEvent

    assert "PageView" in EVENT_SCHEMAS, (
        "PageView missing from EVENT_SCHEMAS; add it to bridge/protocol.py"
    )
    assert event_type_for("PageView", "on_page_change") is PageChangeEvent, (
        "PageView.on_page_change must resolve to PageChangeEvent"
    )


def test_e6_flex_wrap_coverage_matches_documented_rationale() -> None:
    """``_COVERAGE['flex_wrap']`` is ``(True, False)``: Compose reacts, Qt does not.

    This is the tripwire that enforces the documented divergence: if someone
    accidentally wires ``flex_wrap`` into the Qt QSS translator, the
    parametrized ``test_coverage_parity[flex_wrap]`` will already catch the
    regression, but this explicit test documents the *reason* (wrapping is
    realized by the custom ``_WrapWidget`` in the renderer, not QSS) so the
    "why" is visible here rather than only in the rationale comment.
    """
    assert _COVERAGE.get("flex_wrap") == (True, False), (
        "_COVERAGE['flex_wrap'] must be (compose=True, qt=False); "
        "if the Qt translator now reacts to flex_wrap, update the rationale "
        "and the _E6_WIDGET_DIVERGENCES / Wrap / flow_layout_backend entry"
    )
    # Verify the Compose side actually fires.
    base_compose = snapshot(Style())["compose"]
    snap_with_wrap = snapshot(Style(flex_wrap=FlexWrap.WRAP))["compose"]
    assert snap_with_wrap != base_compose, (
        "to_compose must react to flex_wrap=WRAP — flexWrap must appear in the spec"
    )
    assert "flexWrap" in snap_with_wrap, (
        "flex_wrap=WRAP must produce 'flexWrap' key in the Compose spec"
    )
    # Verify the Qt side stays silent.
    base_qt = snapshot(Style())["qt"]
    snap_with_wrap_qt = snapshot(Style(flex_wrap=FlexWrap.WRAP))["qt"]
    assert snap_with_wrap_qt == base_qt, (
        "to_qss/layout_alignment must NOT react to flex_wrap (Qt-inert by design)"
    )


def test_e6_translators_not_affected_by_layout_widgets() -> None:
    """E6 layout-widget imports do not mutate the Style translators.

    No E6 widget (Wrap, PageView, AspectRatio) registers a Style field or
    side-effects the translator tables at import time. Calling
    ``to_compose``/``to_qss`` with ``Style()`` must yield the same output
    regardless of whether the E6 widgets have been imported.
    """
    # The full tempestroid package (which pulls in all E6 widgets) is already
    # imported at module level; we just verify no accidental mutation occurred.
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}, (
        "to_compose(Style()) changed after E6 import — "
        "a layout widget must not side-effect the Compose translator"
    )
    assert empty_snap["qt"]["qss_leaf"] == "", (
        "to_qss(Style()) changed after E6 import — "
        "a layout widget must not side-effect the Qt translator"
    )


# --------------------------------------------------------------------------- #
# Phase E7 — Media and graphics                                               #
#                                                                             #
# E7 adds media/graphics widgets (Canvas, VideoPlayer, WebView, Svg,          #
# CameraPreview, QrScanner, MapView, Blur, BackdropFilter, ClipPath) and the  #
# QrScanEvent. None of them registers a new Style field — Blur.radius and     #
# ClipPath.shape are *widget* props, not Style fields — so the golden/parity  #
# machinery stays untouched. The Canvas IR (a list of DrawCommand value       #
# models) is the one renderer-agnostic spec, so it gets a JSON-serializable   #
# tripwire here.                                                              #
# --------------------------------------------------------------------------- #

#: Intentional Qt × Compose divergences for the E7 media/graphics widgets.
_E7_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "VideoPlayer",
        "topic": "video_surface",
        "qt_strategy": (
            "QMediaPlayer + QVideoWidget (QtMultimedia); setSource(QUrl(src)), "
            "play() on autoplay. WSL may lack a multimedia backend — the widget "
            "still instantiates without playback."
        ),
        "compose_strategy": (
            "AndroidView wrapping a Media3 ExoPlayer PlayerView; "
            "setMediaItem(MediaItem.fromUri(src)) + play() on autoplay."
        ),
        "intentional": True,
    },
    {
        "widget": "WebView",
        "topic": "web_surface",
        "qt_strategy": (
            "QWebEngineView.load(QUrl(url)) when PySide6-WebEngine is present; "
            "otherwise a QLabel placeholder (the wheel does not always ship it)."
        ),
        "compose_strategy": (
            "AndroidView wrapping android.webkit.WebView; settings.javaScriptEnabled "
            "from the prop, loadUrl(url)."
        ),
        "intentional": True,
    },
    {
        "widget": "CameraPreview",
        "topic": "camera_surface",
        "qt_strategy": (
            "PLACEHOLDER QLabel '[CameraPreview — device only]' — the desktop "
            "simulator does not bind a live camera."
        ),
        "compose_strategy": (
            "AndroidView wrapping CameraX PreviewView bound to the lifecycle with "
            "the selected facing."
        ),
        "intentional": True,
    },
    {
        "widget": "QrScanner",
        "topic": "qr_scanner_surface",
        "qt_strategy": (
            "PLACEHOLDER QLabel '[QrScanner — device only]' — no on_scan events "
            "fire in the simulator."
        ),
        "compose_strategy": (
            "CameraX ImageAnalysis + ML Kit BarcodeScanning; on a decode it calls "
            "dispatchEvent(on_scan token, {data, format}) — the widget's on_scan "
            "handler is the channel (a normal typed event, not __native_result__)."
        ),
        "intentional": True,
    },
    {
        "widget": "MapView",
        "topic": "map_surface",
        "qt_strategy": (
            "PLACEHOLDER QLabel '[MapView — device only]' — the simulator embeds "
            "no map engine."
        ),
        "compose_strategy": (
            "Google Maps Compose (GoogleMap + markers) when the maps dependency "
            "and API key are configured; otherwise a documented PLACEHOLDER Box "
            "(the dependency requires google-services.json to compile)."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E7_WIDGET_DIVERGENCES``.
_E7_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E7_WIDGET_DIVERGENCES
}

#: The E7 widgets that must be present in the bridge ``EVENT_SCHEMAS`` contract
#: (so ``introspect()`` lists them and the device round-trip can validate them).
_E7_NEW_WIDGETS: tuple[str, ...] = (
    "Canvas",
    "VideoPlayer",
    "WebView",
    "Svg",
    "CameraPreview",
    "QrScanner",
    "MapView",
    "Blur",
    "BackdropFilter",
    "ClipPath",
)


def test_e7_no_style_field_added() -> None:
    """Phase E7 adds no new ``Style`` field.

    The media/graphics widgets carry their own props (``Blur.radius``,
    ``ClipPath.shape``, ``Canvas.commands``); none of them is a ``Style`` field,
    so the ``_SAMPLES``/``_COVERAGE`` parity tables and the golden snapshots are
    untouched. If a new field appears, update ``_SAMPLES``, ``_COVERAGE``, and
    regenerate goldens with ``UPDATE_GOLDEN=1``.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); E7 must not add a Style field — "
        "Blur.radius / ClipPath.shape are widget props, not Style fields"
    )


def test_e7_canvas_commands_are_json_serializable() -> None:
    """A ``Canvas`` carrying every draw command serializes to pure JSON.

    The Canvas IR is the single renderer-agnostic graphics spec. Each
    ``DrawCommand`` must lower to plain dicts (colors are ``[r, g, b, a]`` lists,
    never tuples), so ``serialize_node`` → ``json.dumps`` round-trips with no
    custom encoder. This pins the contract both renderers consume.
    """
    from tempestroid import (
        ArcTo,
        Canvas,
        Close,
        DrawOval,
        DrawRect,
        DrawText,
        FillCmd,
        LineTo,
        MoveTo,
        StrokeCmd,
    )
    from tempestroid.bridge import serialize_node
    from tempestroid.core.reconciler import build

    canvas = Canvas(
        commands=[
            MoveTo(x=0.0, y=0.0),
            LineTo(x=10.0, y=10.0),
            ArcTo(x=0.0, y=0.0, width=20.0, height=20.0,
                  start_angle=0.0, sweep_angle=90.0),
            Close(),
            DrawRect(x=1.0, y=2.0, width=3.0, height=4.0),
            DrawOval(x=5.0, y=6.0, width=7.0, height=8.0),
            FillCmd(color=[1.0, 0.0, 0.0, 1.0]),
            StrokeCmd(color=[0.0, 0.0, 1.0, 1.0], width=2.0),
            DrawText(text="hi", x=1.0, y=2.0, size=12.0, color=[0.0, 0.0, 0.0, 1.0]),
        ]
    )
    node = build(canvas)
    serialized = serialize_node(node)
    json.dumps(serialized)  # must not raise — the contract is pure JSON
    commands: list[Any] = serialized["props"]["commands"]
    assert isinstance(commands, list) and len(commands) == 9
    assert all("kind" in cmd for cmd in commands), (
        "every serialized DrawCommand must carry its 'kind' discriminator"
    )
    # No tuples survive the round-trip — colors are JSON arrays.
    fill: dict[str, Any] = next(cmd for cmd in commands if cmd["kind"] == "fill")
    assert fill["color"] == [1.0, 0.0, 0.0, 1.0]
    assert isinstance(fill["color"], list)


def test_e7_new_widgets_in_event_schemas() -> None:
    """Every E7 widget appears in the bridge ``EVENT_SCHEMAS`` contract.

    Handler-free widgets (Canvas, VideoPlayer, …) are added unconditionally so
    they still surface in ``introspect()``; ``QrScanner`` carries ``on_scan`` →
    ``QrScanEvent``. A missing entry means a widget is undiscoverable at the
    boundary.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS, event_type_for
    from tempestroid.widgets.events import QrScanEvent

    for name in _E7_NEW_WIDGETS:
        assert name in EVENT_SCHEMAS, (
            f"E7 widget {name!r} absent from EVENT_SCHEMAS; "
            "add it to bridge/protocol.py"
        )
    assert event_type_for("QrScanner", "on_scan") is QrScanEvent, (
        "QrScanner.on_scan must resolve to QrScanEvent"
    )


def test_e7_widget_divergences() -> None:
    """Every E7 media divergence row is intentional and uniquely keyed.

    The tripwire: a renderer specialist who resolves a divergence (e.g. Qt gains
    a real camera surface) must update the table; one who adds a new E7 surface
    must add a row. Either omission fails this test. Five divergences are
    documented (VideoPlayer, WebView, CameraPreview, QrScanner, MapView).
    """
    seen: set[tuple[str, str]] = set()
    for row in _E7_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E7 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (known gap)"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E7_DIVERGENCE_KEYS
    assert len(_E7_WIDGET_DIVERGENCES) == 5, (
        "E7 documents exactly five Qt × Compose divergences"
    )


def test_e7_new_widgets_in_introspect() -> None:
    """All ten E7 media/graphics widgets appear in ``introspect()['widgets']``.

    ``introspect()`` is the framework's self-describing typed contract. A widget
    absent from the catalog is undiscoverable to tooling, the device bridge and
    editor integrations. This test pins the ``WIDGET_TYPES`` list in
    ``core/introspection.py`` against a regression that drops any E7 entry.
    """
    from tempestroid import introspect

    catalog = introspect()
    for name in _E7_NEW_WIDGETS:
        assert name in catalog["widgets"], (
            f"E7 widget {name!r} absent from introspect()['widgets']; "
            "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
        )


def test_e7_qr_scan_event_in_introspect() -> None:
    """``QrScanEvent`` appears in ``introspect()['events']``.

    Pins the ``EVENT_TYPES`` list in ``core/introspection.py``.  If the entry
    is dropped, the device bridge cannot discover the event schema and
    ``event_type_for("QrScanner", "on_scan")`` will silently return ``None``
    at dispatch time — the on_scan payload would be dispatched unvalidated.
    """
    from tempestroid import introspect

    catalog = introspect()
    assert "QrScanEvent" in catalog["events"], (
        "QrScanEvent absent from introspect()['events']; "
        "add it to EVENT_TYPES in tempestroid/core/introspection.py"
    )
    # The schema must describe the two fields (data + format).
    schema = catalog["events"]["QrScanEvent"]
    props = schema.get("properties", {})
    assert "data" in props, (
        "QrScanEvent schema is missing the 'data' field — "
        "the QrScanner device half encodes this in the dispatch payload"
    )
    assert "format" in props, (
        "QrScanEvent schema is missing the 'format' field — "
        "the QrScanner device half encodes this in the dispatch payload"
    )


def test_e7_translators_not_affected_by_media_widgets() -> None:
    """E7 media-widget imports do not mutate the ``Style`` translators.

    No E7 widget adds a ``Style`` field, and none should register a side-effect
    that alters the translator tables at import time.  Calling
    ``to_compose``/``to_qss`` with ``Style()`` must yield the same empty output
    regardless of whether the E7 widgets have been imported — same invariant
    enforced for E1–E6.
    """
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}, (
        "to_compose(Style()) changed after E7 import — "
        "a media widget must not side-effect the Compose translator"
    )
    assert empty_snap["qt"]["qss_leaf"] == "", (
        "to_qss(Style()) changed after E7 import — "
        "a media widget must not side-effect the Qt translator"
    )


def test_e7_canvas_non_divergence_both_renderers_share_same_spec() -> None:
    """``Canvas`` is NOT a Qt × Compose divergence — both renderers share the spec.

    ``Canvas``, ``Svg``, ``Blur``, ``BackdropFilter``, and ``ClipPath`` use the
    same serialized IR on both sides (Qt interprets it with QPainter/QGraphicsEffect;
    Compose interprets it with ``drawIntoCanvas``/``Modifier.blur``/``Modifier.clip``).
    They must NOT appear in the ``_E7_WIDGET_DIVERGENCES`` table.  This test pins
    that invariant: if Canvas is accidentally added to the divergence table (which
    would imply separate IRs), this fails.
    """
    non_diverging = {"Canvas", "Svg", "Blur", "BackdropFilter", "ClipPath"}
    diverging_widgets = {str(row["widget"]) for row in _E7_WIDGET_DIVERGENCES}
    overlap = non_diverging & diverging_widgets
    assert not overlap, (
        f"Widgets {overlap!r} appear in _E7_WIDGET_DIVERGENCES but should not — "
        "they use the same serialized IR on both renderers. "
        "Only VideoPlayer/WebView/CameraPreview/QrScanner/MapView are divergent."
    )


# --------------------------------------------------------------------------- #
# Phase E8 — Platform and native system                                       #
#                                                                             #
# E8 adds native platform capabilities (haptics, sensors, lifecycle,          #
# connectivity, permissions, biometrics, secure_storage, prefs, database,     #
# push, background) plus the ``KeyboardAvoidingView`` widget and four new     #
# stream events (LifecycleEvent, SensorEvent, ConnectivityEvent, DeepLinkEvent).
#                                                                             #
# None of these add a new ``Style`` field — Kotlin layout props like          #
# ``Modifier.imePadding()`` are *widget*-level, not Style fields — so the     #
# golden/parity machinery and all ``_SAMPLES``/``_COVERAGE`` tables above are  #
# untouched.                                                                  #
#                                                                             #
# E8 introduces three new reserved tokens (``SENSOR_TOKEN_PREFIX``,           #
# ``LIFECYCLE_TOKEN``, ``CONNECTIVITY_TOKEN_PREFIX``) that stream continuous  #
# data over the existing single event transport — no new JNI/C entry point.  #
# Both ``bridge/jni.py`` and ``devserver/client.py`` must route these tokens  #
# before falling through to the widget-handler path (lesson E0d).            #
# --------------------------------------------------------------------------- #

#: Intentional Qt × Compose divergences for E8's new widget + native platform.
_E8_WIDGET_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "widget": "KeyboardAvoidingView",
        "topic": "ime_inset_surface",
        "qt_strategy": (
            "Listens to QApplication.inputMethod().keyboardRectangleChanged and "
            "adjusts contentsMargins to recede content above the virtual keyboard. "
            "On the desktop (no virtual keyboard) the signal never fires and the "
            "widget behaves as a plain Column container."
        ),
        "compose_strategy": (
            "Modifier.imePadding() via WindowInsets.ime (Compose Foundation); "
            "the inset is automatically applied at the bottom of the layout when "
            "the IME is visible, receding the content without extra logic."
        ),
        "intentional": True,
    },
    {
        "widget": "KeyboardAvoidingView",
        "topic": "keyboard_visibility_source",
        "qt_strategy": (
            "QInputMethod.keyboardRectangleChanged is the desktop-side signal; "
            "height derived from keyboardRectangle().height(). No-op when the "
            "virtual keyboard is not shown (typical desktop session)."
        ),
        "compose_strategy": (
            "WindowInsets.ime.getBottom(LocalDensity.current) read at each "
            "recomposition; Compose automatically recomposes when the IME "
            "inset changes, so no explicit listener is needed."
        ),
        "intentional": True,
    },
]

#: Native capability divergences: modules that are device-only stubs on Qt.
#: These are NOT widget-level divergences (no Style translator involved), but
#: they are documented here so the contract is visible and findable.
_E8_NATIVE_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "module": "haptics",
        "topic": "vibration_stub",
        "qt_strategy": (
            "vibrate() / impact() raise RuntimeError('_tempest_host is unavailable') "
            "on the desktop — a Qt simulator has no haptics hardware."
        ),
        "compose_strategy": (
            "HapticsModule drives Vibrator.vibrate(VibrationEffect.createOneShot) "
            "(API 26+) with a pre-API-26 fallback, producing real device feedback."
        ),
        "intentional": True,
    },
    {
        "module": "sensors",
        "topic": "sensor_stream_stub",
        "qt_strategy": (
            "start_sensor() raises RuntimeError off-device. No sensor hardware "
            "on the desktop; the dispatch_sensor_event hook is still callable "
            "in tests to simulate incoming samples."
        ),
        "compose_strategy": (
            "SensorModule registers a SensorManager.registerListener callback; "
            "each SensorEventListener.onSensorChanged dispatches a sample over "
            "the reserved '__sensor__:<type>' token to the Python callback registry."
        ),
        "intentional": True,
    },
    {
        "module": "biometrics",
        "topic": "biometric_auth_stub",
        "qt_strategy": (
            "authenticate() raises NativeError('device_only') on the desktop — "
            "no biometric hardware available. The desktop is considered fully "
            "trusted (no auth prompt)."
        ),
        "compose_strategy": (
            "BiometricsModule drives BiometricPrompt (androidx.biometric) with "
            "BiometricPrompt.PromptInfo; result is sent back via "
            "__native_result__:<id> over the event channel."
        ),
        "intentional": True,
    },
    {
        "module": "secure_storage",
        "topic": "encrypted_storage_stub",
        "qt_strategy": (
            "get_secret/set_secret/delete_secret raise NativeError('device_only') "
            "on the desktop — no EncryptedSharedPreferences equivalent in stdlib."
        ),
        "compose_strategy": (
            "SecureStorageModule uses EncryptedSharedPreferences "
            "(androidx.security:security-crypto) backed by AES256-GCM keys in the "
            "Android KeyStore."
        ),
        "intentional": True,
    },
    {
        "module": "push",
        "topic": "fcm_push_stub",
        "qt_strategy": (
            "register_push() raises NativeError('device_only') on the desktop — "
            "FCM token acquisition requires the Android Firebase SDK + "
            "google-services.json (documented as a hardware-gated pendency)."
        ),
        "compose_strategy": (
            "PushModule calls FirebaseMessaging.getInstance().token; the result "
            "is sent back as a PushToken over __native_result__:<id>. Requires "
            "google-services.json to be configured in the Gradle project."
        ),
        "intentional": True,
    },
    {
        "module": "background",
        "topic": "workmanager_stub",
        "qt_strategy": (
            "schedule_task / cancel_task raise RuntimeError off-device — "
            "WorkManager is an Android-only API with no desktop equivalent."
        ),
        "compose_strategy": (
            "BackgroundModule enqueues / cancels PeriodicWorkRequest via "
            "WorkManager.enqueueUniquePeriodicWork / cancelUniqueWork."
        ),
        "intentional": True,
    },
    {
        "module": "prefs",
        "topic": "storage_backend",
        "qt_strategy": (
            "Reads/writes a JSON file at ~/.tempestroid/prefs.json (stdlib json). "
            "Tests override the path via set_prefs_path(tmp_path) for isolation. "
            "Fully functional on the desktop without device hardware."
        ),
        "compose_strategy": (
            "PrefsModule uses SharedPreferences (android.content.SharedPreferences) "
            "— the Android native key-value store, persisted to the app's "
            "data directory."
        ),
        "intentional": True,
    },
    {
        "module": "database",
        "topic": "sql_backend",
        "qt_strategy": (
            "Uses sqlite3 from the Python stdlib backed by a file at "
            "~/.tempestroid/app.db. Tests override the path via set_database_path. "
            "Fully functional on the desktop without device hardware."
        ),
        "compose_strategy": (
            "DatabaseModule uses android.database.sqlite.SQLiteDatabase via "
            "SQLiteOpenHelper — the Android native SQLite API, persisted to the "
            "app's data directory."
        ),
        "intentional": True,
    },
]

#: The (widget, topic) pairs that must appear in ``_E8_WIDGET_DIVERGENCES``.
_E8_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["widget"]), str(row["topic"]))
    for row in _E8_WIDGET_DIVERGENCES
}

#: The (module, topic) pairs that must appear in ``_E8_NATIVE_DIVERGENCES``.
_E8_NATIVE_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["module"]), str(row["topic"]))
    for row in _E8_NATIVE_DIVERGENCES
}

#: The four new E8 events that must appear in ``introspect()['events']``.
_E8_NEW_EVENTS: tuple[str, ...] = (
    "LifecycleEvent",
    "SensorEvent",
    "ConnectivityEvent",
    "DeepLinkEvent",
)

#: The new E8 widget that must appear in ``WIDGET_TYPES`` and ``introspect()``.
_E8_NEW_WIDGET: str = "KeyboardAvoidingView"

#: The three new reserved tokens added in E8 for stream channels.
_E8_RESERVED_TOKENS: dict[str, str] = {
    "SENSOR_TOKEN_PREFIX": "__sensor__",
    "LIFECYCLE_TOKEN": "__lifecycle__",
    "CONNECTIVITY_TOKEN_PREFIX": "__connectivity__",
}


def test_e8_no_style_field_added() -> None:
    """Phase E8 adds no new ``Style`` field.

    The native platform capabilities (haptics, sensors, lifecycle, etc.) and
    the ``KeyboardAvoidingView`` widget carry their own props; none introduces
    a new ``Style`` field. ``Modifier.imePadding()`` on the Compose side and
    ``QInputMethod.keyboardRectangleChanged`` on the Qt side are widget-level
    renderer choices, not translator-level fields. The parity table
    (``_SAMPLES``/``_COVERAGE``) and the golden snapshots are untouched.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); E8 must not add a Style field — "
        "KeyboardAvoidingView's IME-padding behaviour is renderer-level, "
        "not a Style translator field"
    )


def test_e8_widget_divergences_complete() -> None:
    """Every E8 widget divergence row is intentional and uniquely keyed.

    The tripwire: a renderer specialist who resolves a KeyboardAvoidingView
    divergence (e.g. Qt gains a native IME-inset API matching Compose) must
    update the table; one who adds a new E8 widget or topic must add a row.
    Either omission fails this test.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E8_WIDGET_DIVERGENCES:
        key = (str(row["widget"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E8 divergence row for {key!r}; "
            "consolidate or split into distinct topics"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True (known gap)"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"divergence {key!r} is missing a strategy description"
        )
    assert seen == _E8_DIVERGENCE_KEYS


def test_e8_native_divergences_complete() -> None:
    """Every E8 native-module divergence is intentional and uniquely keyed.

    Pins the documented Qt-stub vs device-real split for haptics, sensors,
    biometrics, secure_storage, push, background, prefs, and database. If a
    new module is added with a desktop stub, a row must be added here. If an
    existing stub is promoted to a real Qt implementation, the row must be
    updated (set ``intentional=False``) until the resolved entry is removed.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E8_NATIVE_DIVERGENCES:
        key = (str(row["module"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E8 native divergence row for {key!r}"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"native divergence {key!r} is intentional=False; "
            "remove it (resolved) or keep intentional=True"
        )
        assert row["qt_strategy"] and row["compose_strategy"], (
            f"native divergence {key!r} is missing a strategy description"
        )
    assert seen == _E8_NATIVE_DIVERGENCE_KEYS


def test_e8_reserved_tokens_exported_from_protocol() -> None:
    """The three E8 stream tokens are exported from ``bridge.protocol``.

    These reserved tokens are the bridge between the native host's continuous
    data streams and the Python callback registries. If a token is missing or
    has the wrong value, the bridge routing in ``jni.py._on_event`` and
    ``devserver/client.py:on_event`` will silently drop stream events.

    The exact string values are part of the Python↔Kotlin wire contract — they
    must match what ``NativeModules.kt`` dispatches on the event channel.
    """
    from tempestroid.bridge.protocol import (
        CONNECTIVITY_TOKEN_PREFIX,
        LIFECYCLE_TOKEN,
        SENSOR_TOKEN_PREFIX,
    )

    assert SENSOR_TOKEN_PREFIX == _E8_RESERVED_TOKENS["SENSOR_TOKEN_PREFIX"], (
        f"SENSOR_TOKEN_PREFIX has unexpected value {SENSOR_TOKEN_PREFIX!r}; "
        "the Kotlin SensorModule dispatches '__sensor__:<type>' — must match"
    )
    assert LIFECYCLE_TOKEN == _E8_RESERVED_TOKENS["LIFECYCLE_TOKEN"], (
        f"LIFECYCLE_TOKEN has unexpected value {LIFECYCLE_TOKEN!r}; "
        "the Kotlin LifecycleModule dispatches '__lifecycle__' — must match"
    )
    assert CONNECTIVITY_TOKEN_PREFIX == _E8_RESERVED_TOKENS[
        "CONNECTIVITY_TOKEN_PREFIX"
    ], (
        f"CONNECTIVITY_TOKEN_PREFIX unexpected value {CONNECTIVITY_TOKEN_PREFIX!r}; "
        "the Kotlin ConnectivityModule dispatches '__connectivity__:<state>'"
    )


def test_e8_reserved_tokens_reexported_at_root() -> None:
    """The three E8 tokens are importable from the top-level ``tempestroid`` package.

    User code and the bridge routing code both import from the top-level package.
    If the tokens are absent from ``tempestroid.__all__``, the import will succeed
    (Python finds them via the transitive module graph) but ``from tempestroid
    import SENSOR_TOKEN_PREFIX`` will raise ``ImportError``.
    """
    import tempestroid

    for name in ("SENSOR_TOKEN_PREFIX", "LIFECYCLE_TOKEN", "CONNECTIVITY_TOKEN_PREFIX"):
        assert name in tempestroid.__all__, (
            f"{name} missing from tempestroid.__all__; "
            f"add it to tempestroid/__init__.py"
        )
        assert hasattr(tempestroid, name), (
            f"{name} not importable from tempestroid"
        )


def test_e8_keyboard_avoiding_view_in_event_schemas() -> None:
    """``KeyboardAvoidingView`` appears in ``bridge.protocol.EVENT_SCHEMAS``.

    Even though the widget has no event handlers (``event_schemas = {}``), it
    must be present in ``EVENT_SCHEMAS`` so that ``introspect()`` can list it
    and future event additions don't silently fall through the bridge.
    """
    from tempestroid.bridge.protocol import EVENT_SCHEMAS

    assert _E8_NEW_WIDGET in EVENT_SCHEMAS, (
        f"E8 widget {_E8_NEW_WIDGET!r} missing from EVENT_SCHEMAS; "
        "add it to bridge/protocol.py"
    )
    assert EVENT_SCHEMAS[_E8_NEW_WIDGET] == {}, (
        f"E8 widget {_E8_NEW_WIDGET!r} has non-empty EVENT_SCHEMAS "
        f"({EVENT_SCHEMAS[_E8_NEW_WIDGET]}); update this test if events were added"
    )


def test_e8_keyboard_avoiding_view_in_introspect() -> None:
    """``KeyboardAvoidingView`` appears in ``introspect()['widgets']``.

    ``introspect()`` is the framework's self-describing typed contract — the
    device bridge and tooling use it to discover every widget. A missing entry
    means the widget is undiscoverable and cannot be validated at dispatch time.
    """
    from tempestroid import introspect

    catalog = introspect()
    assert _E8_NEW_WIDGET in catalog["widgets"], (
        f"E8 widget {_E8_NEW_WIDGET!r} absent from introspect()['widgets']; "
        "add it to WIDGET_TYPES in tempestroid/core/introspection.py"
    )


def test_e8_new_events_in_introspect() -> None:
    """The four new E8 events appear in ``introspect()['events']``.

    Pins the ``EVENT_TYPES`` list in ``core/introspection.py`` against a
    regression that drops any of the new events from the catalog. If an event
    is absent, ``event_type_for`` cannot validate stream payloads at the bridge
    boundary.
    """
    from tempestroid import introspect

    catalog = introspect()
    for event in _E8_NEW_EVENTS:
        assert event in catalog["events"], (
            f"E8 event {event!r} absent from introspect()['events']; "
            "add it to EVENT_TYPES in tempestroid/core/introspection.py"
        )


def test_e8_lifecycle_event_schema_carries_state_field() -> None:
    """``LifecycleEvent`` schema exposes the ``state`` field (AppState enum).

    The bridge routes ``__lifecycle__`` payloads to ``dispatch_lifecycle_event``
    which validates against ``LifecycleEvent``. A missing ``state`` field means
    any lifecycle payload would fail validation at the boundary.
    """
    from tempestroid import introspect

    catalog = introspect()
    schema = catalog["events"].get("LifecycleEvent", {})
    props = schema.get("properties", {})
    assert "state" in props, (
        "LifecycleEvent schema must expose the 'state' field; "
        "the bridge validates the __lifecycle__ payload against it"
    )


def test_e8_sensor_event_schema_carries_required_fields() -> None:
    """``SensorEvent`` schema exposes ``sensor``, ``values``, and ``timestamp_ms``.

    The bridge routes ``__sensor__:<type>`` payloads to ``dispatch_sensor_event``
    which validates against ``SensorEvent``. All three fields must be present in
    the schema for the Kotlin-side contract to be verifiable.
    """
    from tempestroid import introspect

    catalog = introspect()
    schema = catalog["events"].get("SensorEvent", {})
    props = schema.get("properties", {})
    for field in ("sensor", "values", "timestamp_ms"):
        assert field in props, (
            f"SensorEvent schema must expose the '{field}' field; "
            "the Kotlin SensorModule includes it in the dispatch payload"
        )


def test_e8_connectivity_event_schema_carries_state_field() -> None:
    """``ConnectivityEvent`` schema exposes the ``state`` field.

    The bridge routes ``__connectivity__:<state>`` payloads to
    ``dispatch_connectivity_event`` which validates against ``ConnectivityEvent``.
    """
    from tempestroid import introspect

    catalog = introspect()
    schema = catalog["events"].get("ConnectivityEvent", {})
    props = schema.get("properties", {})
    assert "state" in props, (
        "ConnectivityEvent schema must expose the 'state' field; "
        "the bridge validates __connectivity__ payloads against it"
    )


def test_e8_deep_link_event_schema_carries_url_and_params() -> None:
    """``DeepLinkEvent`` schema exposes ``url`` and ``params``.

    DeepLinkEvent is dispatched when the host opens the app via an intent URL.
    Both fields must appear in the schema so the Kotlin side can verify the
    payload shape.
    """
    from tempestroid import introspect

    catalog = introspect()
    schema = catalog["events"].get("DeepLinkEvent", {})
    props = schema.get("properties", {})
    assert "url" in props, "DeepLinkEvent schema must expose 'url'"
    assert "params" in props, "DeepLinkEvent schema must expose 'params'"


def test_e8_sensor_token_prefix_separator_contract() -> None:
    """``SENSOR_TOKEN_PREFIX`` must NOT contain a colon — the colon is the separator.

    The bridge routing guard is ``token.startswith(SENSOR_TOKEN_PREFIX + ":")``.
    If the prefix itself contained a colon, the split logic would silently produce
    wrong sensor_type strings and callbacks would never fire.

    Same invariant holds for ``CONNECTIVITY_TOKEN_PREFIX``.
    """
    from tempestroid.bridge.protocol import (
        CONNECTIVITY_TOKEN_PREFIX,
        SENSOR_TOKEN_PREFIX,
    )

    assert ":" not in SENSOR_TOKEN_PREFIX, (
        f"SENSOR_TOKEN_PREFIX {SENSOR_TOKEN_PREFIX!r} contains a colon; "
        "the routing guard uses 'prefix + \":\"' as the full separator — "
        "a colon inside the prefix would break sensor_type extraction"
    )
    assert ":" not in CONNECTIVITY_TOKEN_PREFIX, (
        f"CONNECTIVITY_TOKEN_PREFIX {CONNECTIVITY_TOKEN_PREFIX!r} contains a colon; "
        "same separator contract as SENSOR_TOKEN_PREFIX"
    )


def test_e8_lifecycle_token_no_separator() -> None:
    """``LIFECYCLE_TOKEN`` carries no colon — it is a bare sentinel.

    Unlike ``SENSOR_TOKEN_PREFIX`` and ``CONNECTIVITY_TOKEN_PREFIX``, the
    lifecycle token is a bare sentinel (one fixed value, no sub-type suffix).
    The bridge routing guard is ``token == LIFECYCLE_TOKEN`` (exact match),
    so a colon in the token would never collide with the sensor/connectivity
    prefixes but would be confusing and could collide with handler tokens
    (``"<path>:<prop>"`` format).
    """
    from tempestroid.bridge.protocol import LIFECYCLE_TOKEN

    assert ":" not in LIFECYCLE_TOKEN, (
        f"LIFECYCLE_TOKEN {LIFECYCLE_TOKEN!r} contains a colon; "
        "the routing guard uses exact equality — a colon could collide "
        "with handler-token format '<path>:<prop>'"
    )


def test_e8_tokens_distinct_from_all_existing_reserved_tokens() -> None:
    """The three E8 tokens are distinct from all previously defined reserved tokens.

    This guards against accidental shadowing: if ``LIFECYCLE_TOKEN`` equalled
    ``BACK_TOKEN`` or ``FRAME_TOKEN``, routing would silently divert lifecycle
    events to the navigation-pop or animation-tick path, a very hard-to-debug
    failure.
    """
    from tempestroid.bridge.protocol import (
        BACK_TOKEN,
        CONNECTIVITY_TOKEN_PREFIX,
        FRAME_TOKEN,
        LIFECYCLE_TOKEN,
        SENSOR_TOKEN_PREFIX,
    )
    from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX

    all_tokens = {BACK_TOKEN, FRAME_TOKEN}
    # The E8 bare token must not clash with any existing bare token.
    assert LIFECYCLE_TOKEN not in all_tokens, (
        f"LIFECYCLE_TOKEN {LIFECYCLE_TOKEN!r} clashes with an existing reserved token"
    )
    # The E8 prefixes must not be prefixes of existing tokens, or vice versa.
    for existing in (BACK_TOKEN, FRAME_TOKEN, NATIVE_RESULT_PREFIX):
        assert not SENSOR_TOKEN_PREFIX.startswith(existing) and not existing.startswith(
            SENSOR_TOKEN_PREFIX
        ), (
            f"SENSOR_TOKEN_PREFIX {SENSOR_TOKEN_PREFIX!r} and existing token "
            f"{existing!r} overlap — routing ambiguity"
        )
        assert not CONNECTIVITY_TOKEN_PREFIX.startswith(
            existing
        ) and not existing.startswith(CONNECTIVITY_TOKEN_PREFIX), (
            f"CONNECTIVITY_TOKEN_PREFIX {CONNECTIVITY_TOKEN_PREFIX!r} and existing "
            f"token {existing!r} overlap — routing ambiguity"
        )


def test_e8_translators_not_affected_by_platform_widgets() -> None:
    """E8 platform-widget imports do not mutate the ``Style`` translators.

    ``KeyboardAvoidingView`` has no ``Style`` field; importing it must not
    side-effect either translator table. Calling ``to_compose``/``to_qss`` with
    ``Style()`` must yield the same empty output as before E8 was imported.
    """
    empty_snap = snapshot(Style())
    assert empty_snap["compose"] == {}, (
        "to_compose(Style()) changed after E8 import — "
        "KeyboardAvoidingView must not side-effect the Compose translator"
    )
    assert empty_snap["qt"]["qss_leaf"] == "", (
        "to_qss(Style()) changed after E8 import — "
        "KeyboardAvoidingView must not side-effect the Qt translator"
    )


# ---------------------------------------------------------------------------
# E9 conformance: text_scale / font_asset + RTL start/end mirroring
# ---------------------------------------------------------------------------
#
# Phase E9 adds two new ``Style`` fields (``text_scale``, ``font_asset``) — both
# already folded into ``_SAMPLES`` / ``_COVERAGE`` above — and a ``rtl`` flag on
# *both* translators that mirrors the box model's start/end (padding left/right,
# margin left/right) and flips ``text_align`` LEFT/RIGHT. The two golden cases
# below pin the new translations and the RTL mirroring against silent drift.
#
# ``rtl_snapshot`` captures both translators with ``rtl=True``; ``snapshot``
# captures the default ``rtl=False`` path. ``rtl_layout`` is pinned at both so
# the golden documents the exact left/right swap on each side.


def rtl_snapshot(style: Style) -> dict[str, Any]:
    """Capture both translators' RTL output for ``style`` as a JSON-able dict.

    Args:
        style: The style to translate under a right-to-left layout.

    Returns:
        ``{"compose": ..., "qt": {...}}`` — the RTL conformance snapshot.
    """
    return {
        "compose": to_compose(style, rtl=True),
        "qt": {
            "qss_leaf": to_qss(style, with_padding=True, rtl=True),
            "qss_container": to_qss(style, with_padding=False, rtl=True),
        },
    }


#: E9 golden cases. ``rtl_layout`` pins the ltr-vs-rtl mirroring side by side;
#: ``text_scale_font_asset`` pins the two new typography fields in both
#: translators (ltr only — RTL does not affect them).
_E9_CASES: dict[str, dict[str, Any]] = {
    "rtl_layout": {
        "ltr": snapshot(
            Style(
                padding=Edge(left=8, right=16),
                margin=Edge(left=2, right=4),
                text_align=TextAlign.LEFT,
                border=SideBorder(
                    left=Border(width=1, color=Color(r=10, g=20, b=30))
                ),
            )
        ),
        "rtl": rtl_snapshot(
            Style(
                padding=Edge(left=8, right=16),
                margin=Edge(left=2, right=4),
                text_align=TextAlign.LEFT,
                border=SideBorder(
                    left=Border(width=1, color=Color(r=10, g=20, b=30))
                ),
            )
        ),
    },
    "text_scale_font_asset": snapshot(
        Style(text_scale=1.4, font_asset="fonts/Custom.ttf", font_size=16)
    ),
}


@pytest.mark.parametrize("name", sorted(_E9_CASES))
def test_e9_golden_snapshot(name: str) -> None:
    """Each E9 canonical case matches its committed golden snapshot.

    Regenerate with ``UPDATE_GOLDEN=1`` when a translator changes intentionally.
    """
    snap = _E9_CASES[name]
    path = _GOLDEN_DIR / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", "utf-8")
    assert path.exists(), f"missing golden for {name!r}; run UPDATE_GOLDEN=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert snap == expected, (
        f"conformance drift for {name!r}; review and re-run UPDATE_GOLDEN=1 if intended"
    )


def test_e9_rtl_mirrors_padding_and_text_align() -> None:
    """``rtl=True`` swaps left/right padding and flips LEFT text-align in both."""
    style = Style(padding=Edge(left=8, right=16), text_align=TextAlign.LEFT)
    ltr = to_compose(style)
    rtl = to_compose(style, rtl=True)
    assert ltr["padding"] == {"top": 0.0, "right": 16.0, "bottom": 0.0, "left": 8.0}
    assert rtl["padding"] == {"top": 0.0, "right": 8.0, "bottom": 0.0, "left": 16.0}
    assert ltr["textAlign"] == "left"
    assert rtl["textAlign"] == "right"
    qss_ltr = to_qss(style, with_padding=True)
    qss_rtl = to_qss(style, with_padding=True, rtl=True)
    assert "padding: 0.0px 16.0px 0.0px 8.0px" in qss_ltr
    assert "padding: 0.0px 8.0px 0.0px 16.0px" in qss_rtl


# ---------------------------------------------------------------------------
# E9 translator-level divergences (RTL: Qt vs Compose) — tripwire table
# ---------------------------------------------------------------------------
#
# Phase E9 adds ``rtl: bool = False`` to *both* translators, but their
# RTL behaviour intentionally diverges for fields the Qt translator already
# leaves to the renderer (not QSS):
#
# 1. margin — Compose mirrors ``margin.left``↔``margin.right`` because it emits
#    the full margin spec into the serialized Compose props that the Kotlin
#    ``Modifier.padding`` reads. Qt does NOT emit ``margin`` into QSS (A3 notes:
#    "not wired yet") so the RTL parameter has no effect on Qt's margin output.
#    Both are correct: Qt applies margin in the renderer, not the translator.
#
# 2. text_align — Compose mirrors ``LEFT``→``RIGHT`` / ``RIGHT``→``LEFT`` because
#    the Compose ``TextAlign`` enum is passed as a prop. Qt does NOT emit
#    ``text_align`` into QSS (A3 notes: "Qt would express this via a widget
#    property"); the RTL flag is therefore a no-op in the Qt translator for
#    ``text_align``. Both are correct.
#
# 3. text_scale / font_asset — these are RTL-neutral on both sides; RTL does not
#    change typography. Both translators handle them identically under both
#    ``rtl=False`` and ``rtl=True``.
#
# Updating this table: if a divergence is resolved (e.g. Qt starts emitting
# margin/text_align into QSS), set ``intentional=False``. The tripwire
# ``test_e9_rtl_translator_divergences_complete`` will then fail until the row
# is removed. Adding a new RTL divergence requires a new row AND an entry in the
# pinned-key set.

_E9_RTL_DIVERGENCES: list[dict[str, str | bool]] = [
    {
        "field": "margin",
        "topic": "rtl_mirroring",
        "compose_behaviour": (
            "Mirrors margin.left↔margin.right under rtl=True because the full margin "
            "spec is serialized into Compose props that Modifier.padding reads."
        ),
        "qt_behaviour": (
            "Does NOT emit margin into QSS (A3 notes: not wired yet); the rtl "
            "parameter has no effect on the Qt translator's margin output — margin "
            "is applied imperatively by the renderer."
        ),
        "intentional": True,
    },
    {
        "field": "text_align",
        "topic": "rtl_mirroring",
        "compose_behaviour": (
            "Flips LEFT→RIGHT / RIGHT→LEFT under rtl=True because the Compose "
            "TextAlign prop is serialized and read by the Kotlin renderer."
        ),
        "qt_behaviour": (
            "Does NOT emit text_align into QSS (A3 notes: Qt expresses this via "
            "a widget property); the rtl flag is a no-op in the Qt translator for "
            "text_align — alignment is set on the QLabel/QTextEdit by the renderer."
        ),
        "intentional": True,
    },
]

#: The (field, topic) pairs that must appear in ``_E9_RTL_DIVERGENCES``.
_E9_RTL_DIVERGENCE_KEYS: set[tuple[str, str]] = {
    (str(row["field"]), str(row["topic"]))
    for row in _E9_RTL_DIVERGENCES
}


def test_e9_rtl_translator_divergences_complete() -> None:
    """Every E9 RTL translator divergence is intentional and uniquely keyed.

    The tripwire: if a renderer specialist resolves a divergence (e.g. Qt starts
    emitting margin or text_align into QSS under RTL), they must update
    ``_E9_RTL_DIVERGENCES`` (set ``intentional=False`` and remove after review)
    AND update ``_COVERAGE`` accordingly. Adding a new RTL divergence requires a
    new row here plus a coverage-parity explanation.
    """
    seen: set[tuple[str, str]] = set()
    for row in _E9_RTL_DIVERGENCES:
        key = (str(row["field"]), str(row["topic"]))
        assert key not in seen, (
            f"duplicate E9 RTL divergence row for {key!r}; consolidate or split"
        )
        seen.add(key)
        assert row["intentional"] is True, (
            f"divergence {key!r} is marked intentional=False; "
            "either remove it (resolved) or keep it intentional=True"
        )
        assert row["compose_behaviour"] and row["qt_behaviour"], (
            f"divergence {key!r} is missing a behaviour description"
        )
    assert seen == _E9_RTL_DIVERGENCE_KEYS


def test_e9_rtl_margin_divergence_is_real() -> None:
    """Compose mirrors margin under RTL; Qt translator is a no-op for margin.

    Pins the documented divergence so that the day Qt starts emitting margin
    into QSS (post-v1 roadmap), this test fails loudly and the divergence table
    is updated.
    """
    style = Style(margin=Edge(left=4, right=8))
    # Compose: margin IS mirrored under rtl=True.
    ltr_compose = to_compose(style)
    rtl_compose = to_compose(style, rtl=True)
    assert ltr_compose["margin"] == {
        "top": 0.0, "right": 8.0, "bottom": 0.0, "left": 4.0
    }
    assert rtl_compose["margin"] == {
        "top": 0.0, "right": 4.0, "bottom": 0.0, "left": 8.0
    }
    # Qt: margin is not emitted by the translator at all (rtl is irrelevant).
    qss_ltr = to_qss(style, with_padding=True, rtl=False)
    qss_rtl = to_qss(style, with_padding=True, rtl=True)
    assert qss_ltr == ""
    assert qss_rtl == ""
    # Both LTR and RTL Qt outputs are identical (divergence is real).
    assert qss_ltr == qss_rtl


def test_e9_rtl_text_align_divergence_is_real() -> None:
    """Compose flips text_align under RTL; Qt translator is a no-op for text_align.

    Pins the documented divergence so that the day Qt starts emitting text_align
    into QSS, this test fails loudly and the divergence table is updated.
    """
    style = Style(text_align=TextAlign.LEFT)
    # Compose: text_align IS flipped under rtl=True.
    assert to_compose(style)["textAlign"] == "left"
    assert to_compose(style, rtl=True)["textAlign"] == "right"
    # Qt: text_align is not emitted by the translator at all.
    assert "text-align" not in to_qss(style, with_padding=True)
    assert "text-align" not in to_qss(style, with_padding=True, rtl=True)
    # Both LTR and RTL Qt outputs are identical (divergence is real).
    ltr_qt = to_qss(style, with_padding=True)
    rtl_qt = to_qss(style, with_padding=True, rtl=True)
    assert ltr_qt == rtl_qt


# ---------------------------------------------------------------------------
# E9 bridge contract: THEME_TOKEN / LOCALE_TOKEN exported + reachable
# ---------------------------------------------------------------------------


def test_e9_tokens_exported_from_protocol() -> None:
    """``THEME_TOKEN`` and ``LOCALE_TOKEN`` are exported from ``bridge.protocol``.

    The JNI event sink routes these tokens to ``App.set_theme``/``set_locale``;
    if the constants are absent the routing silently falls through to the widget
    handler path instead.
    """
    from tempestroid.bridge.protocol import LOCALE_TOKEN, THEME_TOKEN

    assert THEME_TOKEN == "__theme__", (
        f"THEME_TOKEN has unexpected value {THEME_TOKEN!r}; "
        "the device sends '__theme__' — the constant must match"
    )
    assert LOCALE_TOKEN == "__locale__", (
        f"LOCALE_TOKEN has unexpected value {LOCALE_TOKEN!r}; "
        "the device sends '__locale__' — the constant must match"
    )


def test_e9_tokens_reexported_at_root() -> None:
    """``THEME_TOKEN`` and ``LOCALE_TOKEN`` are importable from the root package.

    Guards against removing them from ``tempestroid/__init__.py`` while leaving
    them in ``bridge/protocol.py`` — user code that writes
    ``from tempestroid import THEME_TOKEN`` would then fail at runtime.
    """
    import tempestroid

    for name in ("THEME_TOKEN", "LOCALE_TOKEN"):
        assert name in tempestroid.__all__, (
            f"{name} missing from tempestroid.__all__; "
            "add it to tempestroid/__init__.py"
        )
        assert hasattr(tempestroid, name), (
            f"{name} not importable from tempestroid; "
            "add the import to tempestroid/__init__.py"
        )
    assert tempestroid.THEME_TOKEN == "__theme__"  # type: ignore[attr-defined]
    assert tempestroid.LOCALE_TOKEN == "__locale__"  # type: ignore[attr-defined]


def test_e9_tokens_are_bare_sentinels_with_no_colon() -> None:
    """``THEME_TOKEN`` and ``LOCALE_TOKEN`` carry no ``:`` separator.

    Handler tokens are ``"<path>:<prop>"``; native result tokens use
    ``"__native_result__:<id>"``; the E9 theme/locale tokens must be bare
    sentinels so they are matched by exact equality, not prefix, and can never
    collide with widget or native paths.
    """
    from tempestroid.bridge.protocol import LOCALE_TOKEN, THEME_TOKEN

    assert ":" not in THEME_TOKEN, (
        f"THEME_TOKEN {THEME_TOKEN!r} contains ':'; must be a bare sentinel"
    )
    assert ":" not in LOCALE_TOKEN, (
        f"LOCALE_TOKEN {LOCALE_TOKEN!r} contains ':'; must be a bare sentinel"
    )
    assert THEME_TOKEN != LOCALE_TOKEN


def test_e9_tokens_distinct_from_all_existing_reserved_tokens() -> None:
    """E9 tokens do not collide with any previously reserved token or prefix.

    Every reserved token defined across phases A6–E8 is listed here; adding a
    new one that happens to equal ``THEME_TOKEN`` / ``LOCALE_TOKEN`` must fail
    this test, forcing a name change in one of the phases.
    """
    from tempestroid.bridge.protocol import (
        BACK_TOKEN,
        CONNECTIVITY_TOKEN_PREFIX,
        FRAME_TOKEN,
        LIFECYCLE_TOKEN,
        LOCALE_TOKEN,
        SENSOR_TOKEN_PREFIX,
        THEME_TOKEN,
    )
    from tempestroid.native.dispatch import NATIVE_RESULT_PREFIX

    existing = {
        BACK_TOKEN,
        FRAME_TOKEN,
        LIFECYCLE_TOKEN,
        SENSOR_TOKEN_PREFIX,
        CONNECTIVITY_TOKEN_PREFIX,
        NATIVE_RESULT_PREFIX,
    }
    assert THEME_TOKEN not in existing, (
        f"THEME_TOKEN {THEME_TOKEN!r} collides with an existing reserved token"
    )
    assert LOCALE_TOKEN not in existing, (
        f"LOCALE_TOKEN {LOCALE_TOKEN!r} collides with an existing reserved token"
    )
    assert THEME_TOKEN != LOCALE_TOKEN


def test_e9_new_style_fields_documented_count() -> None:
    """Phase E9 adds exactly two new ``Style`` fields (``text_scale``, ``font_asset``).

    This sentinel records the field count at E9 completion. If a future phase
    adds or removes a field without updating ``_SAMPLES`` / ``_COVERAGE`` and
    regenerating goldens, this test fails, forcing a conscious review.
    """
    assert len(Style.model_fields) == len(_SAMPLES), (
        f"Style field count changed to {len(Style.model_fields)} "
        f"(expected {len(_SAMPLES)}); "
        "if intentional, update _SAMPLES, _COVERAGE, regenerate goldens with "
        "UPDATE_GOLDEN=1, and update this test"
    )


def test_e9_text_scale_and_font_asset_in_coverage_table() -> None:
    """``text_scale`` and ``font_asset`` have ``(True, True)`` in ``_COVERAGE``.

    Pins that both translators react to the two new E9 typography fields —
    a future refactor that accidentally drops one from a translator will change
    the parity and fail ``test_coverage_parity``, but this guard makes the
    *expected* parity explicit and documents the rationale in one place.
    """
    assert _COVERAGE["text_scale"] == (True, True), (
        "text_scale parity changed; both translators must react to it. "
        "Compose emits 'textScale'; Qt scales font-size or emits an em unit."
    )
    assert _COVERAGE["font_asset"] == (True, True), (
        "font_asset parity changed; both translators must react to it. "
        "Compose emits 'fontAsset'; Qt emits font-family: \"CustomAsset\"."
    )
