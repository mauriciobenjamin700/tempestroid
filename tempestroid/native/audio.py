"""Native audio capability: microphone capture + speaker playback.

:func:`record_audio` records from the device microphone (request/response — it
resolves with the saved clip when recording stops). :func:`play_sound` and
:func:`stop_sound` drive the device speaker. The Kotlin ``AudioModule`` requests
the ``RECORD_AUDIO`` permission, captures with ``MediaRecorder`` into an
app-private file, and plays back with ``MediaPlayer``, replying over the bridge.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import send_native_request

__all__ = ["AudioClip", "record_audio", "play_sound", "stop_sound"]


class AudioClip(BaseModel):
    """A microphone recording saved on the device.

    Attributes:
        path: Absolute path to the saved audio file (app-private storage).
        duration_ms: Recording length in milliseconds, or ``None`` if unknown.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    duration_ms: int | None = None


async def record_audio(*, max_duration_s: float | None = None) -> AudioClip:
    """Record from the device microphone until stopped or the limit is hit.

    Args:
        max_duration_s: Optional cap on the recording length in seconds; ``None``
            records until :func:`stop_sound`-style host control stops it.

    Returns:
        The captured :class:`AudioClip`.

    Raises:
        NativeError: If the microphone permission is denied (``permission_denied``)
            or capture fails (``unavailable``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request(
        "audio", "record_audio", {"max_duration_s": max_duration_s}
    )
    return AudioClip.model_validate(data)


async def play_sound(src: str, *, volume: float = 1.0) -> None:
    """Play an audio file (path or URL) through the device speaker.

    Resolves once playback has started; raises if the source cannot be opened.

    Args:
        src: A local file path or ``http(s)`` URL to play.
        volume: Playback volume in ``[0.0, 1.0]``.

    Raises:
        NativeError: If the source cannot be played (``unavailable``).
        RuntimeError: If called off-device.
    """
    await send_native_request(
        "audio", "play_sound", {"src": src, "volume": volume}
    )


async def stop_sound() -> None:
    """Stop any audio currently playing through the device speaker.

    Raises:
        RuntimeError: If called off-device.
    """
    await send_native_request("audio", "stop_sound", {})
