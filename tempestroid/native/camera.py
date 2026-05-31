"""Native camera capability.

:func:`take_photo` sends a request/response ``native`` command and awaits the
captured image. The Kotlin ``CameraModule`` requests the camera permission,
launches the ``ACTION_IMAGE_CAPTURE`` intent into an app-private file exposed via
a ``FileProvider``, and replies with the saved path over the bridge.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import send_native_request

__all__ = ["Photo", "take_photo"]


class Photo(BaseModel):
    """A captured photo on the device.

    Attributes:
        path: Absolute path to the saved image file (app-private storage).
        width: Image width in pixels, or ``None`` if the host did not report it.
        height: Image height in pixels, or ``None`` if the host did not report it.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    width: int | None = None
    height: int | None = None


async def take_photo() -> Photo:
    """Capture a photo with the device camera.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the camera permission is denied (``permission_denied``)
            or the user cancels the capture (``cancelled``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request("camera", "take_photo", {})
    return Photo.model_validate(data)
