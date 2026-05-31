"""Native device capabilities (phase B6).

Typed Python APIs over device-native features, driven across the JNI bridge as
``native`` command envelopes (see :mod:`tempestroid.native.dispatch`). The Kotlin
host routes them to capability modules holding the Android ``Context``.
"""

from tempestroid.native.dispatch import native_command, send_native
from tempestroid.native.notifications import notify

__all__ = ["notify", "native_command", "send_native"]
