"""Send native-capability commands across the bridge (phase B6+).

Native capabilities split into two shapes over the same JNI channel the renderer
uses:

* **Fire-and-forget** — a one-way ``{"kind": "native", ...}`` envelope (e.g.
  ``notify``, ``share``). :func:`native_command` builds it; :func:`send_native`
  ships it. No reply.
* **Request/response** — a capability that returns a value (geolocation, camera,
  storage read, clipboard read, bluetooth scan). :func:`send_native_request`
  ships an envelope carrying a ``request_id`` and awaits an
  :class:`asyncio.Future`; the host replies by invoking the *event* channel with
  a reserved token (:data:`NATIVE_RESULT_PREFIX` + the id), which
  :func:`resolve_native_result` matches back to the pending future. This reuses
  the existing ``dispatchEvent`` JNI entry — the native (C) side is unchanged.

The envelope builders are pure (testable); the senders perform the actual
lazy-bound native send, so this module imports cleanly off-device.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any, cast

__all__ = [
    "NATIVE_RESULT_PREFIX",
    "NativeError",
    "native_command",
    "native_request",
    "send_native",
    "send_native_request",
    "resolve_native_result",
]

#: Reserved token prefix the host uses (over the event channel) to deliver a
#: native request/response result back to the matching pending future.
NATIVE_RESULT_PREFIX = "__native_result__:"

#: ``request_id -> Future`` for in-flight :func:`send_native_request` calls.
_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

#: Monotonic source of request ids (deterministic; avoids ``random``/``uuid``).
_request_ids: itertools.count[int] = itertools.count(1)


class NativeError(RuntimeError):
    """A native capability call failed on the device.

    Attributes:
        code: A short machine-readable error code (e.g. ``"permission_denied"``,
            ``"cancelled"``, ``"not_found"``, ``"unavailable"``).
    """

    def __init__(self, code: str, message: str = "") -> None:
        """Initialize the error.

        Args:
            code: The machine-readable error code.
            message: A human-readable detail (optional).
        """
        self.code: str = code
        super().__init__(f"{code}: {message}" if message else code)


def native_command(module: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Build a fire-and-forget native-command envelope.

    Args:
        module: The native module name (e.g. ``"notifications"``).
        action: The action on that module (e.g. ``"notify"``).
        args: JSON-able arguments for the action.

    Returns:
        The serializable command envelope.
    """
    return {"kind": "native", "module": module, "action": action, "args": args}


def native_request(
    module: str, action: str, args: dict[str, Any], request_id: str
) -> dict[str, Any]:
    """Build a request/response native-command envelope.

    Args:
        module: The native module name (e.g. ``"geolocation"``).
        action: The action on that module (e.g. ``"get_position"``).
        args: JSON-able arguments for the action.
        request_id: The correlation id the host echoes back with the result.

    Returns:
        The serializable command envelope, carrying ``request_id``.
    """
    return {
        "kind": "native",
        "module": module,
        "action": action,
        "args": args,
        "request_id": request_id,
    }


def send_native(module: str, action: str, args: dict[str, Any]) -> None:
    """Send a fire-and-forget native-command envelope to the host.

    Args:
        module: The native module name.
        action: The action on that module.
        args: JSON-able arguments for the action.

    Raises:
        RuntimeError: If called off-device (the native host is absent).
    """
    from tempestroid.bridge.jni import native_host

    native_host().send_to_host(json.dumps(native_command(module, action, args)))


async def send_native_request(
    module: str, action: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Send a request/response native command and await the host's result.

    Creates a pending future, ships the envelope (carrying a fresh
    ``request_id``), and suspends until the host calls back through
    :func:`resolve_native_result`. Must be called from the asyncio loop the
    device app runs on (i.e. inside a widget handler).

    Args:
        module: The native module name.
        action: The action on that module.
        args: JSON-able arguments for the action.

    Returns:
        The ``data`` payload of a successful result.

    Raises:
        RuntimeError: If called off-device (the native host is absent).
        NativeError: If the host reports the call failed (``ok`` is false).
    """
    from tempestroid.bridge.jni import native_host

    loop = asyncio.get_running_loop()
    request_id = str(next(_request_ids))
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[request_id] = future
    try:
        native_host().send_to_host(
            json.dumps(native_request(module, action, args, request_id))
        )
        result = await future
    finally:
        _pending.pop(request_id, None)

    if not result.get("ok", False):
        raise NativeError(
            str(result.get("error", "unknown")),
            str(result.get("message", "")),
        )
    data = result.get("data", {})
    return cast("dict[str, Any]", data) if isinstance(data, dict) else {}


def resolve_native_result(request_id: str, payload: dict[str, Any]) -> bool:
    """Resolve a pending native request with the host's result payload.

    Called (on the loop thread) by the JNI event sink when a token prefixed with
    :data:`NATIVE_RESULT_PREFIX` arrives.

    Args:
        request_id: The correlation id parsed from the reserved token.
        payload: The result envelope (``{"ok": ..., "data"/"error": ...}``).

    Returns:
        ``True`` if a matching pending future was resolved, ``False`` otherwise
        (unknown or already-settled id).
    """
    future = _pending.get(request_id)
    if future is None or future.done():
        return False
    future.set_result(payload)
    return True
