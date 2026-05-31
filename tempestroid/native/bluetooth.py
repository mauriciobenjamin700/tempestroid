"""Native Bluetooth capability.

:func:`scan` performs a time-boxed discovery of nearby Bluetooth devices via a
request/response ``native`` command. The Kotlin ``BluetoothModule`` requests the
scan/connect permissions, runs a classic discovery (or BLE scan) for the given
window, and replies with the discovered devices.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import send_native_request

__all__ = ["BluetoothDevice", "scan"]


class BluetoothDevice(BaseModel):
    """A Bluetooth device discovered during a scan.

    Attributes:
        address: The device's hardware (MAC) address — the stable identifier.
        name: The advertised device name, or ``""`` if unnamed.
        rssi: Signal strength in dBm, or ``None`` if not reported.
    """

    model_config = ConfigDict(frozen=True)

    address: str
    name: str = ""
    rssi: int | None = None


async def scan(timeout: float = 8.0) -> list[BluetoothDevice]:
    """Discover nearby Bluetooth devices for a bounded window.

    Args:
        timeout: How long to scan, in seconds.

    Returns:
        The discovered devices, or ``[]`` if none were found.

    Raises:
        NativeError: If a Bluetooth permission is denied (``permission_denied``)
            or the adapter is off/unavailable (``unavailable``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request("bluetooth", "scan", {"timeout": timeout})
    devices = data.get("devices", [])
    if not isinstance(devices, list):
        return []
    return [
        BluetoothDevice.model_validate(device) for device in cast("list[Any]", devices)
    ]
