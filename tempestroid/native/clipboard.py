"""Native clipboard capability.

:func:`set_text` is fire-and-forget (write to the system clipboard);
:func:`get_text` is request/response (read the current clip). The Kotlin
``ClipboardModule`` drives ``ClipboardManager``.
"""

from __future__ import annotations

from tempestroid.native.dispatch import send_native, send_native_request

__all__ = ["set_text", "get_text"]


def set_text(text: str) -> None:
    """Write text to the system clipboard.

    Args:
        text: The text to place on the clipboard.
    """
    send_native("clipboard", "set", {"text": text})


async def get_text() -> str:
    """Read the current text from the system clipboard.

    Returns:
        The clipboard text, or ``""`` if the clipboard is empty or non-text.

    Raises:
        RuntimeError: If called off-device.
    """
    data = await send_native_request("clipboard", "get", {})
    return str(data.get("text", ""))
