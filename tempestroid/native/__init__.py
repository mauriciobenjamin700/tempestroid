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
from tempestroid.native.background import (
    cancel_task,
    dispatch_background_task,
    on_background_task,
    run_device_background,
    schedule_task,
)
from tempestroid.native.biometrics import BiometricResult, authenticate
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
from tempestroid.native.connectivity import (
    ConnectivityCallback,
    dispatch_connectivity_event,
    get_connectivity,
    on_connectivity_change,
)
from tempestroid.native.database import (
    QueryResult,
    execute,
    execute_many,
    set_database_path,
)
from tempestroid.native.dispatch import (
    NATIVE_RESULT_PREFIX,
    NativeError,
    native_command,
    native_request,
    on_device,
    resolve_native_result,
    send_native,
    send_native_request,
)
from tempestroid.native.geolocation import Position, get_position
from tempestroid.native.haptics import ImpactStyle, impact, vibrate
from tempestroid.native.image import decode_image
from tempestroid.native.inference import AarBackend, decode_tensor, encode_tensor
from tempestroid.native.lifecycle import (
    LifecycleCallback,
    dispatch_lifecycle_event,
    on_app_state_change,
)
from tempestroid.native.model_store import ModelStoreError, ensure_model
from tempestroid.native.notifications import notify
from tempestroid.native.permissions import (
    PermissionResult,
    PermissionStatus,
    check_permission,
    request_permission,
)
from tempestroid.native.prefs import (
    delete_pref,
    get_all_prefs,
    get_pref,
    set_pref,
    set_prefs_path,
)
from tempestroid.native.push import (
    PushToken,
    register_push,
    schedule_notification,
)
from tempestroid.native.secure_storage import (
    delete_secret,
    get_secret,
    set_secret,
)
from tempestroid.native.sensors import (
    SensorCallback,
    dispatch_sensor_event,
    start_sensor,
    stop_sensor,
)
from tempestroid.native.share import open_url, share, share_to_whatsapp
from tempestroid.native.storage import (
    delete_file,
    list_files,
    read_file,
    write_file,
)
from tempestroid.native.system import (
    Orientation,
    StatusBarStyle,
    get_brightness,
    keep_awake,
    set_brightness,
    set_orientation,
    set_status_bar,
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
    "on_device",
    # onnx inference (Trilho G)
    "AarBackend",
    "encode_tensor",
    "decode_tensor",
    "decode_image",
    "ensure_model",
    "ModelStoreError",
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
    # haptics (phase E8)
    "ImpactStyle",
    "vibrate",
    "impact",
    # system (phase E8)
    "Orientation",
    "StatusBarStyle",
    "set_status_bar",
    "get_brightness",
    "set_brightness",
    "keep_awake",
    "set_orientation",
    # sensors (phase E8, stream)
    "SensorCallback",
    "start_sensor",
    "stop_sensor",
    "dispatch_sensor_event",
    # lifecycle (phase E8, stream)
    "LifecycleCallback",
    "on_app_state_change",
    "dispatch_lifecycle_event",
    # connectivity (phase E8)
    "ConnectivityCallback",
    "get_connectivity",
    "on_connectivity_change",
    "dispatch_connectivity_event",
    # permissions (phase E8)
    "PermissionStatus",
    "PermissionResult",
    "request_permission",
    "check_permission",
    # biometrics (phase E8)
    "BiometricResult",
    "authenticate",
    # secure storage (phase E8)
    "get_secret",
    "set_secret",
    "delete_secret",
    # preferences (phase E8)
    "get_pref",
    "set_pref",
    "delete_pref",
    "get_all_prefs",
    "set_prefs_path",
    # database (phase E8)
    "QueryResult",
    "execute",
    "execute_many",
    "set_database_path",
    # push (phase E8)
    "PushToken",
    "register_push",
    "schedule_notification",
    # background tasks (phase E8)
    "schedule_task",
    "cancel_task",
    "on_background_task",
    "dispatch_background_task",
    "run_device_background",
]
