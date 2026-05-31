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

from tempestroid.style import AlignItems, JustifyContent, Style

__all__ = ["to_qss", "layout_alignment"]


def to_qss(style: Style | None, *, with_padding: bool) -> str:
    """Render the paint/typography/box parts of a style as a QSS rule body.

    Flex layout (direction/justify/align/grow), gap, and margin are *not* QSS —
    they are applied to the parent ``QBoxLayout`` instead (see
    :func:`layout_alignment` and the renderer). Padding is included only for leaf
    widgets; containers express padding via ``contentsMargins`` to avoid
    double-counting.

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
        rules.append(f"background-color: {style.background.to_rgba_string()}")
    if style.color is not None:
        rules.append(f"color: {style.color.to_rgba_string()}")
    if style.border is not None:
        color = style.border.color.to_rgba_string() if style.border.color else "black"
        rules.append(f"border: {style.border.width}px solid {color}")
    if style.radius is not None:
        rules.append(f"border-radius: {style.radius}px")
    if with_padding and style.padding is not None:
        edge = style.padding
        rules.append(
            f"padding: {edge.top}px {edge.right}px {edge.bottom}px {edge.left}px"
        )
    if style.font_family is not None:
        rules.append(f"font-family: {style.font_family}")
    if style.font_size is not None:
        rules.append(f"font-size: {style.font_size}px")
    if style.font_weight is not None:
        rules.append(f"font-weight: {int(style.font_weight)}")
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
