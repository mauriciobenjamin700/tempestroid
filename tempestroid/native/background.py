"""Native background-task capability (phase E8).

Fire-and-forget scheduling of periodic background work. On the device the Kotlin
``BackgroundModule`` drives ``WorkManager`` (``PeriodicWorkRequest`` /
``cancelUniqueWork``). The Qt simulator has no background scheduler, so both
calls raise off-device.
"""

from __future__ import annotations

from tempestroid.native.dispatch import send_native

__all__ = ["schedule_task", "cancel_task"]


def schedule_task(name: str, *, interval_s: float | None = None) -> None:
    """Schedule (or one-shot enqueue) a named background task.

    Args:
        name: The unique task name (re-scheduling the same name replaces it).
        interval_s: The repeat interval in seconds for a periodic task, or
            ``None`` for a one-shot task.

    Raises:
        RuntimeError: If called off-device (the Qt simulator does not schedule).
    """
    send_native("background", "schedule", {"name": name, "interval_s": interval_s})


def cancel_task(name: str) -> None:
    """Cancel a previously-scheduled background task.

    Args:
        name: The task name to cancel (a no-op when none is scheduled).

    Raises:
        RuntimeError: If called off-device.
    """
    send_native("background", "cancel", {"name": name})
