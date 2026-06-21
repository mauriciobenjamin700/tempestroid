"""Native background-task capability (phase E8).

Schedule named background work that re-enters Python when it fires. On the
device the Kotlin ``BackgroundModule`` drives ``WorkManager`` — a one-shot
``OneTimeWorkRequest`` when ``interval_s`` is ``None`` (runs ~immediately), else
a ``PeriodicWorkRequest`` (15-minute minimum). When the task fires, the host
either dispatches the reserved ``__background__:<name>`` token into the live
interpreter (app alive) or boots a fresh interpreter and calls
:func:`run_device_background` (app process was killed) — both run the handler the
app registered with :func:`on_background_task`.

The Qt simulator has no background scheduler, so :func:`schedule_task` /
:func:`cancel_task` raise off-device.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from tempestroid.native.dispatch import send_native

__all__ = [
    "BackgroundCallback",
    "schedule_task",
    "cancel_task",
    "on_background_task",
    "dispatch_background_task",
    "run_device_background",
]

#: A background-task callback (sync or async), invoked when the named task fires.
BackgroundCallback = Callable[[], "Awaitable[None] | None"]

#: ``task_name -> [callback, ...]`` for the registered background handlers.
_background_handlers: dict[str, list[BackgroundCallback]] = {}


def schedule_task(name: str, *, interval_s: float | None = None) -> None:
    """Schedule (or one-shot enqueue) a named background task.

    Args:
        name: The unique task name (re-scheduling the same name replaces it).
        interval_s: The repeat interval in seconds for a periodic task, or
            ``None`` for a one-shot task that runs as soon as possible.

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


def on_background_task(name: str, callback: BackgroundCallback) -> Callable[[], None]:
    """Register a handler that runs when the named background task fires.

    The app registers handlers at import time (so a freshly-booted interpreter,
    woken by the worker, registers them when it loads the app module). Multiple
    handlers may be registered for the same name.

    Args:
        name: The task name (matches the ``schedule_task`` name).
        callback: Invoked (sync or async) when the task fires.

    Returns:
        An ``unregister`` callable that removes this handler.
    """
    handlers = _background_handlers.setdefault(name, [])
    handlers.append(callback)

    def _unregister() -> None:
        """Remove this handler from the registry."""
        remaining = _background_handlers.get(name)
        if remaining is not None and callback in remaining:
            remaining.remove(callback)
            if not remaining:
                _background_handlers.pop(name, None)

    return _unregister


def dispatch_background_task(name: str) -> None:
    """Run the handlers registered for ``name`` (the task fired).

    Called on the loop thread by the bridge when the host dispatches the reserved
    ``__background__:<name>`` token (the app is alive). An async handler's
    coroutine is scheduled; a sync handler is called directly.

    Args:
        name: The fired task's name.
    """
    import asyncio

    for callback in list(_background_handlers.get(name, [])):
        result = callback()
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)


def run_device_background(zip_path: str, name: str) -> None:
    """Boot-time entry: load the app bundle and run a fired background task.

    The device entry point used when WorkManager wakes a **dead** process: the
    host boots a fresh interpreter and calls this. It extracts the bundled
    project (so the app's ``on_background_task`` registrations run as the module
    loads), then runs the named task's handlers to completion on a fresh event
    loop (so an ``async`` handler finishes before the worker returns).

    Args:
        zip_path: Absolute path to the extracted bundle ``.zip`` on the device.
        name: The fired task's name.
    """
    import asyncio
    from pathlib import Path

    from tempestroid.cli.app_loader import spec_from_project
    from tempestroid.cli.bundle import extract_bundle

    archive = Path(zip_path)
    layout = extract_bundle(archive.read_bytes(), archive.parent / "tempest_app")
    # Loading the entry registers the app's on_background_task handlers.
    spec_from_project(layout.root, layout.entry, name="_tempest_bg")

    async def _run() -> None:
        """Run the named handlers, letting any scheduled coroutines finish."""
        dispatch_background_task(name)
        pending = asyncio.all_tasks() - {asyncio.current_task()}
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(_run())
