"""Python↔Kotlin boundary: serialization, handler dispatch, and transport.

Carries the reconciler's IR/patches to the device renderer and validated events
back. The real device transport is a hand-rolled JNI shim (phase B3, Kotlin
side); this package is the transport-agnostic Python half, fully testable without
a device via :class:`LoopbackBridge`.
"""

from tempestroid.bridge.device import Bridge, DeviceApp, LoopbackBridge
from tempestroid.bridge.handlers import HandlerRegistry
from tempestroid.bridge.jni import (
    JniBridge,
    make_event_sink,
    run_device,
    run_device_bundle,
    run_device_file,
)
from tempestroid.bridge.protocol import (
    BACK_TOKEN,
    DISMISS_TOKEN_PREFIX,
    FRAME_TOKEN,
    EventMessage,
    MountMessage,
    PatchMessage,
    event_type_for,
    handler_token,
)
from tempestroid.bridge.serializer import serialize_node, serialize_patch

__all__ = [
    "Bridge",
    "LoopbackBridge",
    "JniBridge",
    "make_event_sink",
    "run_device",
    "run_device_file",
    "run_device_bundle",
    "DeviceApp",
    "HandlerRegistry",
    "BACK_TOKEN",
    "DISMISS_TOKEN_PREFIX",
    "FRAME_TOKEN",
    "MountMessage",
    "PatchMessage",
    "EventMessage",
    "handler_token",
    "event_type_for",
    "serialize_node",
    "serialize_patch",
]
