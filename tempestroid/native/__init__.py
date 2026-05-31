"""Native device capabilities (phase B6+).

Typed Python APIs over device-native features, driven across the JNI bridge as
``native`` command envelopes (see :mod:`tempestroid.native.dispatch`). The Kotlin
host routes them to capability modules holding the Android ``Context``.

Two shapes:

* **Fire-and-forget** — :func:`notify`, :func:`share`, :func:`share_to_whatsapp`,
  :func:`open_url`, :func:`set_text` (clipboard): one-way commands, no reply.
* **Request/response** — :func:`get_position`, :func:`take_photo`,
  :func:`record_video`, :func:`record_audio`, :func:`play_sound`,
  :func:`stop_sound`,
  :func:`read_file`/:func:`write_file`/:func:`delete_file`/:func:`list_files`,
  :func:`get_text` (clipboard), :func:`scan` (bluetooth): ``await`` a result and
  raise :class:`NativeError` on failure.
"""

from tempestroid.native.audio import (
    AudioClip,
    play_sound,
    record_audio,
    stop_sound,
)
from tempestroid.native.bluetooth import BluetoothDevice, scan
from tempestroid.native.camera import (
    CameraFacing,
    Photo,
    Video,
    VideoQuality,
    record_video,
    take_photo,
)
from tempestroid.native.clipboard import get_text, set_text
from tempestroid.native.dispatch import (
    NATIVE_RESULT_PREFIX,
    NativeError,
    native_command,
    native_request,
    resolve_native_result,
    send_native,
    send_native_request,
)
from tempestroid.native.geolocation import Position, get_position
from tempestroid.native.notifications import notify
from tempestroid.native.share import open_url, share, share_to_whatsapp
from tempestroid.native.storage import (
    delete_file,
    list_files,
    read_file,
    write_file,
)

__all__ = [
    # dispatch core
    "NATIVE_RESULT_PREFIX",
    "NativeError",
    "native_command",
    "native_request",
    "send_native",
    "send_native_request",
    "resolve_native_result",
    # notifications
    "notify",
    # geolocation
    "Position",
    "get_position",
    # share
    "share",
    "share_to_whatsapp",
    "open_url",
    # camera
    "CameraFacing",
    "VideoQuality",
    "Photo",
    "Video",
    "take_photo",
    "record_video",
    # audio (microphone + speaker)
    "AudioClip",
    "record_audio",
    "play_sound",
    "stop_sound",
    # storage
    "read_file",
    "write_file",
    "delete_file",
    "list_files",
    # clipboard
    "get_text",
    "set_text",
    # bluetooth
    "BluetoothDevice",
    "scan",
]
