"""Native push-notification capability (phase E8).

:func:`register_push` is request/response (returns the FCM registration token);
:func:`schedule_notification` is fire-and-forget (a local notification scheduled
``delay_s`` in the future). On the device the Kotlin ``PushModule`` drives
``FirebaseMessaging`` (token) and the notification scheduler. The Qt simulator
has no FCM, so :func:`register_push` raises ``device_only`` and
:func:`schedule_notification` likewise raises off-device.

Device pendency: the FCM half needs ``google-services.json`` configured on the
host; without it the Kotlin module replies ``not_configured``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import (
    NativeError,
    on_device,
    send_native,
    send_native_request,
)

__all__ = ["PushToken", "register_push", "schedule_notification"]


class PushToken(BaseModel):
    """An FCM push-registration token.

    Attributes:
        token: The opaque device registration token to send to a push backend.
    """

    model_config = ConfigDict(frozen=True)

    token: str


async def register_push() -> PushToken:
    """Register for push notifications and return the FCM token.

    Returns:
        The device's :class:`PushToken`.

    Raises:
        NativeError: On the Qt simulator (``device_only``), or ``not_configured``
            when ``google-services.json`` is absent on the host.
    """
    if not on_device():
        raise NativeError("device_only", "push is not supported on Qt simulator")
    data = await send_native_request("push", "register", {})
    return PushToken.model_validate(data)


def schedule_notification(title: str, body: str, delay_s: float) -> None:
    """Schedule a local notification to post after a delay.

    Args:
        title: The notification title.
        body: The notification body text.
        delay_s: Seconds from now to post the notification.

    Raises:
        RuntimeError: If called off-device (the Qt simulator does not schedule).
    """
    send_native(
        "push",
        "schedule_notification",
        {"title": title, "body": body, "delay_s": delay_s},
    )
