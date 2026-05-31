"""Native notifications capability (phase B6).

A thin typed Python API over the device's notification system. Calling
:func:`notify` from a handler sends a ``native`` command across the bridge; the
Kotlin ``NotificationModule`` posts it via ``NotificationManager``.
"""

from __future__ import annotations

from tempestroid.native.dispatch import send_native

__all__ = ["notify"]


def notify(title: str, body: str = "") -> None:
    """Post a system notification on the device.

    Args:
        title: The notification title.
        body: The notification body text.
    """
    send_native("notifications", "notify", {"title": title, "body": body})
