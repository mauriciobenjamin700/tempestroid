"""Translate a typed ``Style`` into Qt's vocabulary (QSS + layout config).

Qt is a clean target for the web-like style model: QSS is already a CSS-like
language (padding/border/background/radius map almost directly), and
``QBoxLayout`` is flex-like (direction + alignment + stretch ≈ flex-direction +
justify/align + flex-grow).

This module is one of the two ``Style`` translators the conformance suite (phase
D) pins against each other; keeping it pure and small is what keeps the desktop
simulator honest against the Compose device renderer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from tempestroid.style import (
    AlignItems,
    Border,
    Color,
    Corners,
    FontStyle,
    Gradient,
    GradientDirection,
    JustifyContent,
    SideBorder,
    Style,
    TextDecoration,
)

__all__ = ["to_qss", "layout_alignment", "self_alignment"]

_FONT_STYLE: dict[FontStyle, str] = {
    FontStyle.NORMAL: "normal",
    FontStyle.ITALIC: "italic",
}
_TEXT_DECORATION: dict[TextDecoration, str] = {
    TextDecoration.NONE: "none",
    TextDecoration.UNDERLINE: "underline",
    TextDecoration.LINE_THROUGH: "line-through",
}
#: QSS ``qlineargradient`` axis coordinates per gradient direction.
_GRADIENT_COORDS: dict[GradientDirection, tuple[int, int, int, int]] = {
    GradientDirection.TOP_BOTTOM: (0, 0, 0, 1),
    GradientDirection.BOTTOM_TOP: (0, 1, 0, 0),
    GradientDirection.LEFT_RIGHT: (0, 0, 1, 0),
    GradientDirection.RIGHT_LEFT: (1, 0, 0, 0),
}


def _qss_background(background: Color | Gradient) -> str:
    """Render a background as a QSS ``background-color`` value (color or gradient)."""
    if isinstance(background, Gradient):
        x1, y1, x2, y2 = _GRADIENT_COORDS[background.direction]
        stops = ", ".join(
            f"stop:{stop.position} {stop.color.to_rgba_string()}"
            for stop in background.stops
        )
        return f"qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2}, {stops})"
    return background.to_rgba_string()


def _qss_border_value(border: Border) -> str:
    """Render a uniform :class:`Border` as a QSS ``Npx solid color`` value."""
    color = border.color.to_rgba_string() if border.color else "black"
    return f"{border.width}px solid {color}"


def _qss_border_rules(border: Border | SideBorder) -> list[str]:
    """Render a border (uniform or per-side) as QSS declarations."""
    if isinstance(border, SideBorder):
        rules: list[str] = []
        for side, value in (
            ("top", border.top),
            ("right", border.right),
            ("bottom", border.bottom),
            ("left", border.left),
        ):
            if value is not None:
                rules.append(f"border-{side}: {_qss_border_value(value)}")
        return rules
    return [f"border: {_qss_border_value(border)}"]


def _qss_radius_rules(radius: float | Corners) -> list[str]:
    """Render a radius (uniform or per-corner) as QSS declarations."""
    if isinstance(radius, Corners):
        return [
            f"border-top-left-radius: {radius.top_left}px",
            f"border-top-right-radius: {radius.top_right}px",
            f"border-bottom-right-radius: {radius.bottom_right}px",
            f"border-bottom-left-radius: {radius.bottom_left}px",
        ]
    return [f"border-radius: {radius}px"]


def to_qss(style: Style | None, *, with_padding: bool) -> str:
    """Render the paint/typography/box parts of a style as a QSS rule body.

    Flex layout (direction/justify/align/grow) and gap are *not* QSS — they are
    applied to the parent ``QBoxLayout`` instead (see :func:`layout_alignment` and
    the renderer). ``opacity``/``shadow`` are applied as ``QGraphicsEffect``s by
    the renderer, and ``letter_spacing`` via ``QFont``, so they are not emitted
    here either. ``margin`` *is* emitted as a QSS box-model rule (outer spacing,
    distinct from ``padding``). Padding is included only for leaf widgets;
    containers express padding via ``contentsMargins`` to avoid double-counting —
    margin has no such conflict, so it is always emitted.

    Args:
        style: The style to translate, or ``None``.
        with_padding: Whether to emit ``padding`` (leaves: yes; containers: no).

    Returns:
        A ``"; "``-joined QSS declaration body (empty string when nothing maps).
    """
    if style is None:
        return ""
    rules: list[str] = []
    if style.background is not None:
        rules.append(f"background-color: {_qss_background(style.background)}")
    if style.color is not None:
        rules.append(f"color: {style.color.to_rgba_string()}")
    if style.border is not None:
        rules.extend(_qss_border_rules(style.border))
    if style.radius is not None:
        rules.extend(_qss_radius_rules(style.radius))
    if with_padding and style.padding is not None:
        edge = style.padding
        rules.append(
            f"padding: {edge.top}px {edge.right}px {edge.bottom}px {edge.left}px"
        )
    if style.margin is not None:
        edge = style.margin
        rules.append(
            f"margin: {edge.top}px {edge.right}px {edge.bottom}px {edge.left}px"
        )
    if style.font_family is not None:
        rules.append(f"font-family: {style.font_family}")
    if style.font_size is not None:
        rules.append(f"font-size: {style.font_size}px")
    if style.font_weight is not None:
        rules.append(f"font-weight: {int(style.font_weight)}")
    if style.font_style is not None:
        rules.append(f"font-style: {_FONT_STYLE[style.font_style]}")
    if style.text_decoration is not None:
        rules.append(f"text-decoration: {_TEXT_DECORATION[style.text_decoration]}")
    if style.min_width is not None:
        rules.append(f"min-width: {style.min_width}px")
    if style.max_width is not None:
        rules.append(f"max-width: {style.max_width}px")
    if style.min_height is not None:
        rules.append(f"min-height: {style.min_height}px")
    if style.max_height is not None:
        rules.append(f"max-height: {style.max_height}px")
    return "; ".join(rules)


_MAIN_ROW: dict[JustifyContent, Qt.AlignmentFlag] = {
    JustifyContent.START: Qt.AlignmentFlag.AlignLeft,
    JustifyContent.CENTER: Qt.AlignmentFlag.AlignHCenter,
    JustifyContent.END: Qt.AlignmentFlag.AlignRight,
}
_MAIN_COLUMN: dict[JustifyContent, Qt.AlignmentFlag] = {
    JustifyContent.START: Qt.AlignmentFlag.AlignTop,
    JustifyContent.CENTER: Qt.AlignmentFlag.AlignVCenter,
    JustifyContent.END: Qt.AlignmentFlag.AlignBottom,
}
_CROSS_ROW: dict[AlignItems, Qt.AlignmentFlag] = {
    AlignItems.START: Qt.AlignmentFlag.AlignTop,
    AlignItems.CENTER: Qt.AlignmentFlag.AlignVCenter,
    AlignItems.END: Qt.AlignmentFlag.AlignBottom,
}
_CROSS_COLUMN: dict[AlignItems, Qt.AlignmentFlag] = {
    AlignItems.START: Qt.AlignmentFlag.AlignLeft,
    AlignItems.CENTER: Qt.AlignmentFlag.AlignHCenter,
    AlignItems.END: Qt.AlignmentFlag.AlignRight,
}


def layout_alignment(
    *,
    is_row: bool,
    justify: JustifyContent | None,
    align: AlignItems | None,
) -> Qt.AlignmentFlag | None:
    """Map flex justify/align to a combined Qt alignment flag.

    ``START``/``CENTER``/``END`` map cleanly. ``AlignItems.STRETCH`` and the
    ``SPACE_*`` justify values have no single-flag equivalent and fall through to
    Qt's default packing (a documented v1 limit; ``SPACE_*`` lands post-v1).

    Args:
        is_row: Whether the container's main axis is horizontal (``Row``).
        justify: Main-axis distribution, or ``None``.
        align: Cross-axis alignment, or ``None``.

    Returns:
        The combined alignment flag, or ``None`` when nothing maps (use Qt's
        default).
    """
    flag = Qt.AlignmentFlag(0)
    main_map = _MAIN_ROW if is_row else _MAIN_COLUMN
    cross_map = _CROSS_ROW if is_row else _CROSS_COLUMN
    if justify is not None and justify in main_map:
        flag |= main_map[justify]
    if align is not None and align in cross_map:
        flag |= cross_map[align]
    return flag if flag != Qt.AlignmentFlag(0) else None


def self_alignment(
    *, is_row: bool, align_self: AlignItems | None
) -> Qt.AlignmentFlag | None:
    """Map a child's ``align_self`` to a cross-axis Qt alignment flag.

    The per-child analogue of :func:`layout_alignment`'s cross-axis half:
    ``align_self`` overrides the container's ``align`` for one child.
    ``STRETCH`` has no single-flag equivalent and falls through to Qt's default.

    Args:
        is_row: Whether the parent container's main axis is horizontal (``Row``).
        align_self: The child's cross-axis override, or ``None``.

    Returns:
        The cross-axis alignment flag, or ``None`` when nothing maps.
    """
    if align_self is None:
        return None
    cross_map = _CROSS_ROW if is_row else _CROSS_COLUMN
    return cross_map.get(align_self)
