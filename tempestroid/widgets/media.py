"""Media leaf widgets: ``Image`` and ``Icon``.

These are non-interactive leaves (no events): they carry a source/name plus
presentation hints, and the leaf renderer turns them into a platform image or
icon. Sizing and color come from the shared :class:`~tempestroid.style.Style`.
"""

from __future__ import annotations

from enum import StrEnum

from tempestroid.widgets.base import Widget

__all__ = ["ImageFit", "Image", "Icon"]


class ImageFit(StrEnum):
    """How an image scales to fill its box (CSS ``object-fit`` vocabulary)."""

    CONTAIN = "contain"
    COVER = "cover"
    FILL = "fill"
    NONE = "none"


class Image(Widget):
    """A bitmap image loaded from a URL or asset path.

    Attributes:
        src: The image source — an ``http(s)`` URL or a bundled asset path.
        fit: How the image scales within its box.
        alt: Alternative text shown if the image cannot be loaded.
    """

    src: str
    fit: ImageFit = ImageFit.CONTAIN
    alt: str = ""


class Icon(Widget):
    """A vector icon from the platform's icon set.

    Attributes:
        name: The icon identifier (e.g. a Material Icons name like ``"home"``).
        size: The icon's edge length in logical pixels, or ``None`` for the
            renderer default.
    """

    name: str
    size: float | None = None
