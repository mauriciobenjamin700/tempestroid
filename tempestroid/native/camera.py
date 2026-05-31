"""Native camera capability: photo + video capture.

:func:`take_photo` and :func:`record_video` send request/response ``native``
commands and await the captured media. The Kotlin ``CameraModule`` requests the
camera (and, for video, microphone) permission, launches the
``ACTION_IMAGE_CAPTURE`` / ``ACTION_VIDEO_CAPTURE`` intent into an app-private
file exposed via a ``FileProvider``, and replies with the saved path over the
bridge.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import send_native_request

__all__ = [
    "CameraFacing",
    "VideoQuality",
    "Photo",
    "Video",
    "take_photo",
    "record_video",
]


class CameraFacing(StrEnum):
    """Which physical camera to open."""

    BACK = "back"
    FRONT = "front"


class VideoQuality(StrEnum):
    """Capture quality hint passed to the device camera app."""

    LOW = "low"
    HIGH = "high"


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


class Video(BaseModel):
    """A captured video on the device.

    Attributes:
        path: Absolute path to the saved video file (app-private storage).
        duration_ms: Clip length in milliseconds, or ``None`` if unknown.
        width: Frame width in pixels, or ``None`` if the host did not report it.
        height: Frame height in pixels, or ``None`` if the host did not report it.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None


async def take_photo(
    *,
    camera: CameraFacing = CameraFacing.BACK,
    max_width: int | None = None,
    max_height: int | None = None,
) -> Photo:
    """Capture a photo with the device camera.

    Args:
        camera: Which camera to open (back or front).
        max_width: Optional cap on the saved image width in pixels (the host
            downscales to fit while preserving aspect ratio); ``None`` keeps the
            device default.
        max_height: Optional cap on the saved image height in pixels.

    Returns:
        The captured :class:`Photo`.

    Raises:
        NativeError: If the camera permission is denied (``permission_denied``)
            or the user cancels the capture (``cancelled``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request(
        "camera",
        "take_photo",
        {"camera": camera.value, "max_width": max_width, "max_height": max_height},
    )
    return Photo.model_validate(data)


async def record_video(
    *,
    camera: CameraFacing = CameraFacing.BACK,
    max_duration_s: float | None = None,
    quality: VideoQuality = VideoQuality.HIGH,
) -> Video:
    """Record a video with the device camera.

    Args:
        camera: Which camera to open (back or front).
        max_duration_s: Optional cap on the clip length in seconds (the camera
            app stops recording at the limit); ``None`` leaves it open-ended.
        quality: Capture quality hint (``LOW``/``HIGH``).

    Returns:
        The captured :class:`Video`.

    Raises:
        NativeError: If the camera/microphone permission is denied
            (``permission_denied``) or the user cancels the capture
            (``cancelled``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request(
        "camera",
        "record_video",
        {
            "camera": camera.value,
            "max_duration_s": max_duration_s,
            "quality": quality.value,
        },
    )
    return Video.model_validate(data)
