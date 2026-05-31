"""Typed, web-like inline style model.

This module borrows the *vocabulary* of CSS (flexbox, box model, typography)
expressed as validated Pydantic objects, while deliberately dropping the CSS
*machine*: there are no selectors, no specificity and no implicit cascade.
Every style is explicit, validated and predictable.

The same ``Style`` object is later translated by two leaf renderers
(``Style -> Qt`` and ``Style -> Compose``); keeping it backend-agnostic here is
what allows the desktop simulator to stay honest against the device.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "FlexDirection",
    "JustifyContent",
    "AlignItems",
    "TextAlign",
    "FontWeight",
    "Color",
    "Edge",
    "Border",
    "Style",
]


class FlexDirection(StrEnum):
    """Main-axis direction of a flex container (``flex-direction``)."""

    ROW = "row"
    COLUMN = "column"


class JustifyContent(StrEnum):
    """Distribution of children along the main axis (``justify-content``)."""

    START = "start"
    END = "end"
    CENTER = "center"
    SPACE_BETWEEN = "space-between"
    SPACE_AROUND = "space-around"
    SPACE_EVENLY = "space-evenly"


class AlignItems(StrEnum):
    """Alignment of children along the cross axis (``align-items``)."""

    START = "start"
    END = "end"
    CENTER = "center"
    STRETCH = "stretch"


class TextAlign(StrEnum):
    """Horizontal text alignment (``text-align``)."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class FontWeight(IntEnum):
    """Common font weights, matching the CSS numeric scale."""

    THIN = 100
    LIGHT = 300
    NORMAL = 400
    MEDIUM = 500
    SEMIBOLD = 600
    BOLD = 700
    BLACK = 900


class Color(BaseModel):
    """An RGBA color.

    Construct it directly, from a hex string via :meth:`from_hex`, or by passing
    a hex string anywhere a ``Color`` is expected (a ``before`` validator coerces
    ``str`` into a ``Color``).

    Attributes:
        r: Red channel, 0-255.
        g: Green channel, 0-255.
        b: Blue channel, 0-255.
        a: Alpha channel, 0.0 (transparent) to 1.0 (opaque).
    """

    model_config = ConfigDict(frozen=True)

    r: int = Field(ge=0, le=255)
    g: int = Field(ge=0, le=255)
    b: int = Field(ge=0, le=255)
    a: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> object:
        """Coerce a hex string into the channel mapping Pydantic expects.

        Args:
            value: Raw input — either a hex string or an already-shaped mapping.

        Returns:
            A ``dict`` of channels when given a string, otherwise ``value``
            unchanged.
        """
        if isinstance(value, str):
            r, g, b, a = cls._parse_hex(value)
            return {"r": r, "g": g, "b": b, "a": a}
        return value

    @staticmethod
    def _parse_hex(value: str) -> tuple[int, int, int, float]:
        """Parse a ``#RGB``/``#RRGGBB``/``#RRGGBBAA`` string into channels.

        Args:
            value: The hex string, with or without a leading ``#``.

        Returns:
            The ``(r, g, b, a)`` channels — RGB as 0-255 ints, alpha as 0.0-1.0.

        Raises:
            ValueError: If the string is not a valid hex color.
        """
        text = value.lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) not in (6, 8):
            raise ValueError(f"invalid hex color: {value!r}")
        try:
            r = int(text[0:2], 16)
            g = int(text[2:4], 16)
            b = int(text[4:6], 16)
            a = int(text[6:8], 16) / 255 if len(text) == 8 else 1.0
        except ValueError as exc:
            raise ValueError(f"invalid hex color: {value!r}") from exc
        return r, g, b, a

    @classmethod
    def from_hex(cls, value: str) -> Color:
        """Build a color from a hex string.

        Args:
            value: A ``#RGB``, ``#RRGGBB`` or ``#RRGGBBAA`` string.

        Returns:
            The parsed color.

        Raises:
            ValueError: If the string is not a valid hex color.
        """
        r, g, b, a = cls._parse_hex(value)
        return cls(r=r, g=g, b=b, a=a)

    @classmethod
    def rgba(cls, r: int, g: int, b: int, a: float = 1.0) -> Color:
        """Build a color from explicit channel values.

        Args:
            r: Red channel, 0-255.
            g: Green channel, 0-255.
            b: Blue channel, 0-255.
            a: Alpha channel, 0.0-1.0.

        Returns:
            The constructed color.
        """
        return cls(r=r, g=g, b=b, a=a)

    def to_hex(self) -> str:
        """Render the color as ``#RRGGBB`` (or ``#RRGGBBAA`` when translucent).

        Returns:
            The hex representation.
        """
        base = f"#{self.r:02x}{self.g:02x}{self.b:02x}"
        if self.a < 1.0:
            return f"{base}{round(self.a * 255):02x}"
        return base

    def to_rgba_string(self) -> str:
        """Render the color as a CSS-style ``rgba(...)`` string.

        Returns:
            The ``rgba(r, g, b, a)`` representation.
        """
        return f"rgba({self.r}, {self.g}, {self.b}, {self.a})"


class Edge(BaseModel):
    """Per-side spacing in logical pixels (used for padding and margin)."""

    model_config = ConfigDict(frozen=True)

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    @classmethod
    def all(cls, value: float) -> Edge:
        """Build an edge with the same spacing on every side.

        Args:
            value: Spacing applied to all four sides.

        Returns:
            The constructed edge.
        """
        return cls(top=value, right=value, bottom=value, left=value)

    @classmethod
    def symmetric(cls, *, vertical: float = 0.0, horizontal: float = 0.0) -> Edge:
        """Build an edge with mirrored vertical and horizontal spacing.

        Args:
            vertical: Spacing for the top and bottom sides.
            horizontal: Spacing for the left and right sides.

        Returns:
            The constructed edge.
        """
        return cls(top=vertical, bottom=vertical, left=horizontal, right=horizontal)


class Border(BaseModel):
    """A uniform border (``border-width`` + ``border-color``)."""

    model_config = ConfigDict(frozen=True)

    width: float = 0.0
    color: Color | None = None


class Style(BaseModel):
    """An inline, typed style object.

    Every field is optional: ``None`` means "unset", letting the leaf renderer
    fall back to its own default. Styles are frozen; combine them with
    :meth:`merge` to layer overrides without mutation.
    """

    model_config = ConfigDict(frozen=True)

    # Flexbox layout.
    direction: FlexDirection | None = None
    justify: JustifyContent | None = None
    align: AlignItems | None = None
    grow: float | None = None
    gap: float | None = None

    # Box model.
    padding: Edge | None = None
    margin: Edge | None = None
    border: Border | None = None
    radius: float | None = None

    # Paint.
    background: Color | None = None
    color: Color | None = None

    # Typography.
    font_family: str | None = None
    font_size: float | None = None
    font_weight: FontWeight | None = None
    text_align: TextAlign | None = None

    # Dimensions (logical pixels).
    width: float | None = None
    height: float | None = None
    min_width: float | None = None
    max_width: float | None = None
    min_height: float | None = None
    max_height: float | None = None

    def merge(self, other: Style) -> Style:
        """Layer another style on top of this one.

        Fields explicitly set on ``other`` (i.e. not ``None``) win; everything
        else is inherited from ``self``.

        Args:
            other: The overriding style.

        Returns:
            A new, merged style.
        """
        overrides = other.model_dump(exclude_none=True)
        return self.model_copy(update=overrides)
