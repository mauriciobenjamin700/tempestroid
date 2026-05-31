"""Translate a typed ``Style`` into a serializable Compose spec (``Style → Compose``).

The device renderer is Kotlin/Jetpack Compose, so this side cannot build a
``Modifier`` directly — instead it emits a small JSON-able dict that the Kotlin
renderer turns into ``Row``/``Column`` + ``Arrangement`` + ``Alignment`` +
``Modifier`` at runtime. This is the second of the two ``Style`` translators the
conformance suite (phase D) pins against ``Style → Qt``; keeping it pure data
makes that comparison possible without a device.

Mapping (plan §4.2): ``direction`` → Row/Column (decided by the widget type on
the Kotlin side), ``justify`` → ``Arrangement``, ``align`` → ``Alignment``,
``grow`` → ``Modifier.weight``, box model → ``Modifier`` chain.
"""

from __future__ import annotations

from typing import Any

from tempestroid.style import AlignItems, JustifyContent, Style, TextAlign

__all__ = ["to_compose"]

_JUSTIFY: dict[JustifyContent, str] = {
    JustifyContent.START: "start",
    JustifyContent.END: "end",
    JustifyContent.CENTER: "center",
    JustifyContent.SPACE_BETWEEN: "spaceBetween",
    JustifyContent.SPACE_AROUND: "spaceAround",
    JustifyContent.SPACE_EVENLY: "spaceEvenly",
}
_ALIGN: dict[AlignItems, str] = {
    AlignItems.START: "start",
    AlignItems.END: "end",
    AlignItems.CENTER: "center",
    AlignItems.STRETCH: "stretch",
}
_TEXT_ALIGN: dict[TextAlign, str] = {
    TextAlign.LEFT: "left",
    TextAlign.CENTER: "center",
    TextAlign.RIGHT: "right",
    TextAlign.JUSTIFY: "justify",
}


def to_compose(style: Style | None) -> dict[str, Any]:
    """Translate a style into a Compose spec dict.

    Keys are omitted when unset, so the Kotlin renderer applies its own default
    (mirrors how ``Style → Qt`` leaves unset fields to Qt).

    Args:
        style: The style to translate, or ``None``.

    Returns:
        A JSON-serializable dict of Compose hints (empty when ``style`` is
        ``None`` or fully unset).
    """
    if style is None:
        return {}
    spec: dict[str, Any] = {}
    if style.justify is not None:
        spec["arrangement"] = _JUSTIFY[style.justify]
    if style.align is not None:
        spec["alignment"] = _ALIGN[style.align]
    if style.grow is not None:
        spec["weight"] = style.grow
    if style.gap is not None:
        spec["gap"] = style.gap
    if style.padding is not None:
        edge = style.padding
        spec["padding"] = {
            "top": edge.top,
            "right": edge.right,
            "bottom": edge.bottom,
            "left": edge.left,
        }
    if style.margin is not None:
        edge = style.margin
        spec["margin"] = {
            "top": edge.top,
            "right": edge.right,
            "bottom": edge.bottom,
            "left": edge.left,
        }
    if style.background is not None:
        spec["background"] = style.background.to_hex()
    if style.color is not None:
        spec["color"] = style.color.to_hex()
    if style.border is not None:
        spec["border"] = {
            "width": style.border.width,
            "color": style.border.color.to_hex() if style.border.color else None,
        }
    if style.radius is not None:
        spec["radius"] = style.radius
    if style.font_family is not None:
        spec["fontFamily"] = style.font_family
    if style.font_size is not None:
        spec["fontSize"] = style.font_size
    if style.font_weight is not None:
        spec["fontWeight"] = int(style.font_weight)
    if style.text_align is not None:
        spec["textAlign"] = _TEXT_ALIGN[style.text_align]
    for name, value in (
        ("width", style.width),
        ("height", style.height),
        ("minWidth", style.min_width),
        ("maxWidth", style.max_width),
        ("minHeight", style.min_height),
        ("maxHeight", style.max_height),
    ):
        if value is not None:
            spec[name] = value
    return spec
