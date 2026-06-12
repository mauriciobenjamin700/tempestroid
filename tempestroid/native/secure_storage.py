"""Native secure key-value storage capability (phase E8).

Backed on the device by ``EncryptedSharedPreferences`` (Android Keystore). The
get is request/response; set/delete are fire-and-forget. The Qt simulator has no
hardware-backed keystore, so all three raise
:class:`~tempestroid.native.dispatch.NativeError` with the ``device_only`` code —
secrets must not silently fall back to plaintext on the desktop.
"""

from __future__ import annotations

from tempestroid.native.dispatch import (
    NativeError,
    on_device,
    send_native,
    send_native_request,
)

__all__ = ["get_secret", "set_secret", "delete_secret"]


def _require_device() -> None:
    """Raise unless running on the device.

    Raises:
        NativeError: On the Qt simulator (``device_only``).
    """
    if not on_device():
        raise NativeError("device_only", "secure storage not supported on Qt simulator")


async def get_secret(key: str) -> str | None:
    """Read a secret value from encrypted storage.

    Args:
        key: The secret's key.

    Returns:
        The decrypted value, or ``None`` when the key is absent.

    Raises:
        NativeError: On the Qt simulator (``device_only``).
    """
    _require_device()
    data = await send_native_request("secure_storage", "get", {"key": key})
    value = data.get("value")
    return str(value) if value is not None else None


def set_secret(key: str, value: str) -> None:
    """Write a secret value to encrypted storage.

    Args:
        key: The secret's key.
        value: The value to encrypt and store.

    Raises:
        NativeError: On the Qt simulator (``device_only``).
    """
    _require_device()
    send_native("secure_storage", "set", {"key": key, "value": value})


def delete_secret(key: str) -> None:
    """Delete a secret from encrypted storage.

    Args:
        key: The secret's key (a no-op when absent).

    Raises:
        NativeError: On the Qt simulator (``device_only``).
    """
    _require_device()
    send_native("secure_storage", "delete", {"key": key})
