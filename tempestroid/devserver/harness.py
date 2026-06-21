"""Device-side glue for the F9 UI-test harness over the dev server.

When the dev server runs in harness mode (``DevServer(harness=True)``), the
device's code-push client must do two extra things beyond the normal serve loop:

1. **Mirror outgoing renders back to the host.** Every ``mount``/``patch``
   message the :class:`~tempestroid.bridge.device.DeviceApp` sends over the real
   bridge is *also* POSTed to the dev server, which applies it to a host-side
   :class:`~tempest_core.core.ir.Scene` mirror the test driver reads.
2. **Pull host→device events and dispatch them.** The host enqueues
   ``{token, payload}`` events; the client long-polls ``/poll`` and feeds each to
   the device's event sink — the *same* path a real Compose tap takes — so the
   resulting rebuild flows back through (1).

:class:`HarnessTransport` is the bridge wrapper for (1); :func:`poll_commands` is
the loop for (2). Both are transport-agnostic (the HTTP ``post``/``fetch`` and the
event ``sink`` are injected) so they unit-test with an in-memory transport, no
``adb`` and no emulator.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from tempestroid.bridge.device import Bridge

__all__ = ["HarnessTransport", "poll_commands"]


class HarnessTransport(Bridge):
    """A bridge that forwards to a real bridge and mirrors renders to the host.

    Wraps the device's real :class:`~tempestroid.bridge.device.Bridge` so the
    device still renders normally (the inner bridge drives the Compose tree),
    while every ``mount``/``patch`` message is additionally POSTed to the dev
    server's harness endpoints, keeping the host-side mirror in step.

    Attributes:
        inner: The wrapped real bridge.
    """

    def __init__(
        self,
        inner: Bridge,
        post: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Initialize the harness transport.

        Args:
            inner: The real device bridge to forward every message to.
            post: Async ``(path, body) -> None`` that POSTs ``body`` as JSON to
                the dev server (e.g. ``("/mount", {...})``).
        """
        self.inner: Bridge = inner
        self._post = post

    async def send(self, message: dict[str, Any]) -> None:
        """Forward a message to the inner bridge and mirror it to the host.

        Args:
            message: A serialized ``mount`` / ``patch`` message.
        """
        await self.inner.send(message)
        kind = message.get("kind")
        if kind == "mount":
            await self._post("/mount", message)
        elif kind == "patch":
            await self._post("/patch", message)


async def poll_commands(
    url: str,
    *,
    sink: Callable[[str, str], None],
    fetch: Callable[[str], Awaitable[bytes]],
    poll_interval: float = 0.05,
    max_polls: int | None = None,
) -> None:
    """Long-poll the host→device command queue and feed each event to the sink.

    Each ``GET /poll`` returns either a queued ``{token, payload}`` event or
    ``{"token": null}`` when the server's long-poll window elapsed with nothing
    queued. A real event is handed to ``sink(token, payload_json)`` — the exact
    callback a Compose tap drives — so it flows through ``DeviceApp.handle_event``
    and rebuilds the UI.

    Args:
        url: The dev server base URL.
        sink: The device event sink (``token``, ``payload_json``) — the same one
            ``run_dev_client`` registers for real taps.
        fetch: Async ``url -> body`` HTTP GET returning raw bytes.
        poll_interval: Seconds to wait after an empty poll before re-polling.
        max_polls: Stop after this many polls (tests); ``None`` runs forever.
    """
    polls = 0
    while max_polls is None or polls < max_polls:
        polls += 1
        try:
            body = json.loads((await fetch(f"{url}/poll")).decode("utf-8"))
        except Exception:  # noqa: BLE001 - keep polling on any transient error
            await asyncio.sleep(poll_interval)
            continue
        token = body.get("token")
        if token is None:
            await asyncio.sleep(poll_interval)
            continue
        payload: dict[str, Any] = body.get("payload", {})
        sink(token, json.dumps(payload))
