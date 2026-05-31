"""Send native-capability commands across the bridge (phase B6).

Native capabilities (notifications, camera, …) are driven from Python by sending
a ``{"kind": "native", ...}`` envelope over the same JNI channel the renderer
uses. The Kotlin host routes ``native`` envelopes to a registered module handler
(which has the Android ``Context``) instead of the Compose tree.

The envelope builder is pure (testable); :func:`send_native` performs the actual
lazy-bound native send, so this module imports cleanly off-device.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["native_command", "send_native"]


def native_command(module: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Build a native-command envelope.

    Args:
        module: The native module name (e.g. ``"notifications"``).
        action: The action on that module (e.g. ``"notify"``).
        args: JSON-able arguments for the action.

    Returns:
        The serializable command envelope.
    """
    return {"kind": "native", "module": module, "action": action, "args": args}


def send_native(module: str, action: str, args: dict[str, Any]) -> None:
    """Send a native-command envelope to the host over the bridge.

    Args:
        module: The native module name.
        action: The action on that module.
        args: JSON-able arguments for the action.

    Raises:
        RuntimeError: If called off-device (the native host is absent).
    """
    from tempestroid.bridge.jni import native_host

    native_host().send_to_host(json.dumps(native_command(module, action, args)))
