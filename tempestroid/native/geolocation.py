"""Native geolocation capability.

A typed Python API over the device's location services. :func:`get_position`
sends a request/response ``native`` command and awaits the host's fix; the Kotlin
``GeolocationModule`` requests the location permission, reads a single fix via
``FusedLocationProvider``/``LocationManager``, and replies over the bridge.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestroid.native.dispatch import send_native_request

__all__ = ["Position", "get_position"]


class Position(BaseModel):
    """A geographic position fix returned by the device.

    Attributes:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        accuracy: Horizontal accuracy radius in meters (``0.0`` if unknown).
        altitude: Altitude in meters above sea level, or ``None`` if unavailable.
    """

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float
    accuracy: float = 0.0
    altitude: float | None = None


async def get_position(high_accuracy: bool = True) -> Position:
    """Request a single location fix from the device.

    Args:
        high_accuracy: Prefer GPS over coarse network location when ``True``.

    Returns:
        The current device :class:`Position`.

    Raises:
        NativeError: If the location permission is denied (``permission_denied``)
            or no fix is available (``unavailable``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request(
        "geolocation", "get_position", {"high_accuracy": high_accuracy}
    )
    return Position.model_validate(data)
