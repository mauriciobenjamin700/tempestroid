"""Native system capability: status bar, brightness, wake-lock, orientation.

Mixed-shape module: the setters (:func:`set_status_bar`, :func:`set_brightness`,
:func:`keep_awake`, :func:`set_orientation`) are fire-and-forget; the getter
:func:`get_brightness` is request/response. The Kotlin ``SystemModule`` drives
``WindowInsetsController`` (status bar), ``Settings.System.SCREEN_BRIGHTNESS``,
``FLAG_KEEP_SCREEN_ON`` and ``ActivityInfo.screenOrientation``. On the Qt
simulator there is no system chrome to drive, so the setters raise off-device
and :func:`get_brightness` likewise has no device to query.
"""

from __future__ import annotations

from enum import StrEnum

from tempestroid.native.dispatch import send_native, send_native_request

__all__ = [
    "Orientation",
    "StatusBarStyle",
    "set_status_bar",
    "get_brightness",
    "set_brightness",
    "keep_awake",
    "set_orientation",
]


class Orientation(StrEnum):
    """A screen-orientation lock the app can request."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    AUTO = "auto"


class StatusBarStyle(StrEnum):
    """The status-bar foreground (icon/text) style."""

    LIGHT = "light"
    DARK = "dark"


def set_status_bar(
    *,
    hidden: bool | None = None,
    color: str | None = None,
    style: StatusBarStyle | None = None,
) -> None:
    """Configure the system status bar.

    Args:
        hidden: When given, show/hide the status bar.
        color: When given, the status-bar background as a ``#rrggbb`` hex string.
        style: When given, the foreground icon/text style (light/dark).

    Raises:
        RuntimeError: If called off-device.
    """
    send_native(
        "system",
        "set_status_bar",
        {
            "hidden": hidden,
            "color": color,
            "style": style.value if style is not None else None,
        },
    )


async def get_brightness() -> float:
    """Read the current screen brightness.

    Returns:
        The brightness in the ``[0.0, 1.0]`` range.

    Raises:
        RuntimeError: If called off-device.
    """
    data = await send_native_request("system", "get_brightness", {})
    return float(data.get("value", 0.0))


def set_brightness(value: float) -> None:
    """Set the screen brightness.

    Args:
        value: The target brightness in the ``[0.0, 1.0]`` range.

    Raises:
        RuntimeError: If called off-device.
    """
    send_native("system", "set_brightness", {"value": value})


def keep_awake(enabled: bool) -> None:
    """Keep the screen on (or release the wake-lock).

    Args:
        enabled: ``True`` to hold the screen awake, ``False`` to release.

    Raises:
        RuntimeError: If called off-device.
    """
    send_native("system", "keep_awake", {"enabled": enabled})


def set_orientation(orientation: Orientation) -> None:
    """Lock (or auto) the screen orientation.

    Args:
        orientation: The requested orientation lock.

    Raises:
        RuntimeError: If called off-device.
    """
    send_native("system", "set_orientation", {"orientation": orientation.value})
