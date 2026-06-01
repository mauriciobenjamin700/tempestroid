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

from tempestroid.style import (
    AlignItems,
    Border,
    Color,
    Corners,
    Curve,
    Edge,
    FlexWrap,
    FontStyle,
    Gradient,
    GradientDirection,
    JustifyContent,
    Position,
    SideBorder,
    StackAlign,
    Style,
    TextAlign,
    TextDecoration,
    TextOverflow,
)

__all__ = ["to_compose"]

_CURVE: dict[Curve, str] = {
    Curve.LINEAR: "linear",
    Curve.EASE_IN: "easeIn",
    Curve.EASE_OUT: "easeOut",
    Curve.EASE_IN_OUT: "easeInOut",
    Curve.EASE: "ease",
    Curve.BOUNCE: "bounce",
    Curve.ELASTIC: "elastic",
}

_FLEX_WRAP: dict[FlexWrap, str] = {
    FlexWrap.NOWRAP: "nowrap",
    FlexWrap.WRAP: "wrap",
    FlexWrap.WRAP_REVERSE: "wrapReverse",
}

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
_FONT_STYLE: dict[FontStyle, str] = {
    FontStyle.NORMAL: "normal",
    FontStyle.ITALIC: "italic",
}
_TEXT_DECORATION: dict[TextDecoration, str] = {
    TextDecoration.NONE: "none",
    TextDecoration.UNDERLINE: "underline",
    TextDecoration.LINE_THROUGH: "lineThrough",
}
_TEXT_OVERFLOW: dict[TextOverflow, str] = {
    TextOverflow.CLIP: "clip",
    TextOverflow.ELLIPSIS: "ellipsis",
}
_STACK_ALIGN: dict[StackAlign, str] = {
    StackAlign.TOP_START: "topStart",
    StackAlign.TOP_CENTER: "topCenter",
    StackAlign.TOP_END: "topEnd",
    StackAlign.CENTER_START: "centerStart",
    StackAlign.CENTER: "center",
    StackAlign.CENTER_END: "centerEnd",
    StackAlign.BOTTOM_START: "bottomStart",
    StackAlign.BOTTOM_CENTER: "bottomCenter",
    StackAlign.BOTTOM_END: "bottomEnd",
}
_POSITION: dict[Position, str] = {
    Position.STATIC: "static",
    Position.ABSOLUTE: "absolute",
}
_GRADIENT_DIRECTION: dict[GradientDirection, str] = {
    GradientDirection.TOP_BOTTOM: "topBottom",
    GradientDirection.BOTTOM_TOP: "bottomTop",
    GradientDirection.LEFT_RIGHT: "leftRight",
    GradientDirection.RIGHT_LEFT: "rightLeft",
}


def _border_spec(border: Border) -> dict[str, Any]:
    """Serialize a uniform :class:`Border` to a Compose-spec dict."""
    return {
        "width": border.width,
        "color": border.color.to_hex() if border.color else None,
    }


def _background_spec(background: Color | Gradient) -> str | dict[str, Any]:
    """Serialize a background: a hex string for a color, a dict for a gradient."""
    if isinstance(background, Gradient):
        return {
            "kind": "gradient",
            "direction": _GRADIENT_DIRECTION[background.direction],
            "stops": [
                {"color": stop.color.to_hex(), "position": stop.position}
                for stop in background.stops
            ],
        }
    return background.to_hex()


#: ``text-align`` values whose meaning flips under a right-to-left layout.
_TEXT_ALIGN_RTL_MIRROR: dict[TextAlign, TextAlign] = {
    TextAlign.LEFT: TextAlign.RIGHT,
    TextAlign.RIGHT: TextAlign.LEFT,
}


def _mirror_edge(edge: Edge) -> dict[str, float]:
    """Serialize an :class:`~tempestroid.style.Edge` with left/right swapped.

    Args:
        edge: The edge to mirror.

    Returns:
        The edge dict with ``left`` and ``right`` exchanged.
    """
    return {
        "top": edge.top,
        "right": edge.left,
        "bottom": edge.bottom,
        "left": edge.right,
    }


def to_compose(style: Style | None, *, rtl: bool = False) -> dict[str, Any]:
    """Translate a style into a Compose spec dict.

    Keys are omitted when unset, so the Kotlin renderer applies its own default
    (mirrors how ``Style → Qt`` leaves unset fields to Qt).

    Args:
        style: The style to translate, or ``None``.
        rtl: Whether the node lays out right-to-left. When ``True``, the
            ``start``/``end`` of the box model is mirrored — ``padding.left`` ↔
            ``padding.right``, ``margin.left`` ↔ ``margin.right`` — and a
            ``text_align`` of ``LEFT``/``RIGHT`` is flipped, matching the Qt
            translator so the two renderers stay in lockstep.

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
    if style.align_self is not None:
        spec["alignSelf"] = _ALIGN[style.align_self]
    if style.grow is not None:
        spec["weight"] = style.grow
    if style.gap is not None:
        spec["gap"] = style.gap
    if style.flex_wrap is not None:
        spec["flexWrap"] = _FLEX_WRAP[style.flex_wrap]
    if style.padding is not None:
        edge = style.padding
        spec["padding"] = (
            _mirror_edge(edge)
            if rtl
            else {
                "top": edge.top,
                "right": edge.right,
                "bottom": edge.bottom,
                "left": edge.left,
            }
        )
    if style.margin is not None:
        edge = style.margin
        spec["margin"] = (
            _mirror_edge(edge)
            if rtl
            else {
                "top": edge.top,
                "right": edge.right,
                "bottom": edge.bottom,
                "left": edge.left,
            }
        )
    if style.background is not None:
        spec["background"] = _background_spec(style.background)
    if style.color is not None:
        spec["color"] = style.color.to_hex()
    if style.opacity is not None:
        spec["opacity"] = style.opacity
    if style.shadow is not None:
        shadow = style.shadow
        spec["shadow"] = {
            "color": shadow.color.to_hex() if shadow.color else None,
            "blur": shadow.blur,
            "offsetX": shadow.offset_x,
            "offsetY": shadow.offset_y,
        }
    if style.border is not None:
        if isinstance(style.border, SideBorder):
            spec["border"] = {
                side: _border_spec(value) if value is not None else None
                for side, value in (
                    ("top", style.border.top),
                    ("right", style.border.right),
                    ("bottom", style.border.bottom),
                    ("left", style.border.left),
                )
            }
        else:
            spec["border"] = _border_spec(style.border)
    if style.radius is not None:
        if isinstance(style.radius, Corners):
            spec["radius"] = {
                "topLeft": style.radius.top_left,
                "topRight": style.radius.top_right,
                "bottomRight": style.radius.bottom_right,
                "bottomLeft": style.radius.bottom_left,
            }
        else:
            spec["radius"] = style.radius
    if style.transition is not None:
        spec["transition"] = {
            "durationMs": style.transition.duration_ms,
            "curve": _CURVE[style.transition.curve],
            "delayMs": style.transition.delay_ms,
        }
    if style.font_family is not None:
        spec["fontFamily"] = style.font_family
    if style.font_size is not None:
        spec["fontSize"] = style.font_size
    if style.font_weight is not None:
        spec["fontWeight"] = int(style.font_weight)
    if style.font_style is not None:
        spec["fontStyle"] = _FONT_STYLE[style.font_style]
    if style.text_align is not None:
        text_align = (
            _TEXT_ALIGN_RTL_MIRROR.get(style.text_align, style.text_align)
            if rtl
            else style.text_align
        )
        spec["textAlign"] = _TEXT_ALIGN[text_align]
    if style.text_decoration is not None:
        spec["textDecoration"] = _TEXT_DECORATION[style.text_decoration]
    if style.letter_spacing is not None:
        spec["letterSpacing"] = style.letter_spacing
    if style.line_height is not None:
        spec["lineHeight"] = style.line_height
    if style.max_lines is not None:
        spec["maxLines"] = style.max_lines
    if style.text_overflow is not None:
        spec["textOverflow"] = _TEXT_OVERFLOW[style.text_overflow]
    if style.text_scale is not None:
        spec["textScale"] = style.text_scale
    if style.font_asset is not None:
        spec["fontAsset"] = style.font_asset
    if style.stack_align is not None:
        spec["stackAlign"] = _STACK_ALIGN[style.stack_align]
    if style.position is not None:
        spec["position"] = _POSITION[style.position]
    for name, value in (
        ("top", style.top),
        ("right", style.right),
        ("bottom", style.bottom),
        ("left", style.left),
    ):
        if value is not None:
            spec[name] = value
    for name, value in (
        ("width", style.width),
        ("height", style.height),
        ("minWidth", style.min_width),
        ("maxWidth", style.max_width),
        ("minHeight", style.min_height),
        ("maxHeight", style.max_height),
        ("aspectRatio", style.aspect_ratio),
    ):
        if value is not None:
            spec[name] = value
    return spec
