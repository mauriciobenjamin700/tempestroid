"""Native sensor streams (phase E8).

Sensors are *continuous*: instead of a one-shot request/response, opening a
sensor registers a Python callback and tells the host to start streaming. The
host then pushes one :class:`~tempestroid.widgets.events.SensorEvent` per sample
over the **existing event channel** under the reserved token
``"__sensor__:<type>"`` — no new JNI/C entry point. The bridge
(:mod:`tempestroid.bridge.jni` and :mod:`tempestroid.devserver.client`) routes
that token to :func:`dispatch_sensor_event`, which validates the payload and
fans it out to the registered callbacks.

The callback registry is module-global. :func:`start_sensor` returns a ``stop``
callable that both unregisters the callback and tells the host to stop the
stream (when it was the last listener), so a recreated ``DeviceApp`` (hot-reload)
can tear its streams down cleanly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tempestroid.native.dispatch import send_native
from tempestroid.widgets.events import SensorEvent, SensorType

__all__ = [
    "SensorCallback",
    "start_sensor",
    "stop_sensor",
    "dispatch_sensor_event",
]

#: A sensor-sample callback (sync or async).
SensorCallback = Callable[[SensorEvent], "Awaitable[None] | None"]

#: ``sensor_type -> [callback, ...]`` for the open sensor streams.
_sensor_callbacks: dict[str, list[SensorCallback]] = {}


def start_sensor(
    sensor: SensorType,
    callback: SensorCallback,
    rate_ms: int = 100,
) -> Callable[[], None]:
    """Open a sensor stream and register a per-sample callback.

    Tells the host to start sampling ``sensor`` at ``rate_ms`` and registers
    ``callback`` to receive each :class:`SensorEvent`. The host streams samples
    over the reserved sensor token, routed back through
    :func:`dispatch_sensor_event`.

    Args:
        sensor: Which sensor to open.
        callback: Invoked with each sample (sync or async).
        rate_ms: The requested sampling period in milliseconds.

    Returns:
        A ``stop`` callable that unregisters this callback and stops the host
        stream once no callbacks remain for the sensor.

    Raises:
        RuntimeError: If called off-device.
    """
    callbacks = _sensor_callbacks.setdefault(sensor.value, [])
    callbacks.append(callback)
    send_native("sensors", "start", {"sensor": sensor.value, "rate_ms": rate_ms})

    def _stop() -> None:
        """Unregister this callback and stop the stream when it was the last."""
        remaining = _sensor_callbacks.get(sensor.value)
        if remaining is not None and callback in remaining:
            remaining.remove(callback)
            if not remaining:
                _sensor_callbacks.pop(sensor.value, None)
                stop_sensor(sensor)

    return _stop


def stop_sensor(sensor: SensorType) -> None:
    """Stop a sensor stream on the host and drop all its callbacks.

    Args:
        sensor: The sensor whose stream to stop.

    Raises:
        RuntimeError: If called off-device.
    """
    _sensor_callbacks.pop(sensor.value, None)
    send_native("sensors", "stop", {"sensor": sensor.value})


def dispatch_sensor_event(sensor_type: str, payload: dict[str, Any]) -> None:
    """Dispatch a host sensor sample to the registered callbacks.

    Called on the loop thread by the bridge when a ``"__sensor__:<type>"`` token
    arrives. The raw payload is validated into a :class:`SensorEvent` (the
    sensor is taken from the token so the host need not echo it) before fan-out;
    an async callback's coroutine is scheduled, a sync callback is called
    directly.

    Args:
        sensor_type: The sensor type parsed from the reserved token.
        payload: The raw sample payload.
    """
    import asyncio

    callbacks = _sensor_callbacks.get(sensor_type)
    if not callbacks:
        return
    raw: dict[str, Any] = {"sensor": sensor_type, **payload}
    event = SensorEvent.model_validate(raw)
    for callback in list(callbacks):
        result = callback(event)
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)
