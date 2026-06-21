"""Native haptics capability (phase E8).

Fire-and-forget vibration and impact feedback. :func:`vibrate` and
:func:`impact` send ``native`` commands across the bridge; the Kotlin
``HapticsModule`` drives ``Vibrator``/``VibrationEffect``. On the Qt simulator
the underlying :func:`~tempestroid.native.dispatch.send_native` raises off-device
(there is no ``_tempest_host``) — a desktop has no haptics hardware.
"""

from __future__ import annotations

from enum import StrEnum

from tempestroid.native.dispatch import send_native

__all__ = ["ImpactStyle", "vibrate", "impact"]


class ImpactStyle(StrEnum):
    """The intensity of a haptic impact tap.

    Attributes:
        LIGHT: A subtle, low-energy tap — for confirming minor interactions
            such as a toggle flip or selection change.
        MEDIUM: A moderate tap with noticeably more force than ``LIGHT`` — for
            standard button presses and routine confirmations.
        HEAVY: A strong, pronounced tap — for emphasizing significant events
            such as completing an action or hitting a boundary.
    """

    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


def vibrate(duration_ms: int = 50) -> None:
    """Vibrate the device for a fixed duration.

    Args:
        duration_ms: The vibration length in milliseconds.

    Raises:
        RuntimeError: If called off-device (the Qt simulator has no haptics).
    """
    send_native("haptics", "vibrate", {"duration_ms": duration_ms})


def impact(style: ImpactStyle = ImpactStyle.MEDIUM) -> None:
    """Play a short impact haptic of the given intensity.

    Args:
        style: The impact intensity (light/medium/heavy).

    Raises:
        RuntimeError: If called off-device (the Qt simulator has no haptics).
    """
    send_native("haptics", "impact", {"style": style.value})
