"""Native device storage capability.

A typed API over the app's private files directory. Reads/writes/deletes/lists
are request/response ``native`` commands; the Kotlin ``StorageModule`` resolves
names against ``Context.filesDir`` (sandboxed, no permission needed).

``read_file`` follows the single-resource convention — a missing file raises
``NativeError("not_found")``. ``list_files`` follows the collection convention —
it returns ``[]`` when the directory is empty, never raises.
"""

from __future__ import annotations

from typing import Any, cast

from tempestroid.native.dispatch import send_native_request

__all__ = ["read_file", "write_file", "delete_file", "list_files"]


async def write_file(name: str, content: str) -> None:
    """Write text to an app-private file, creating or overwriting it.

    Args:
        name: The file name (relative to the app's private files directory).
        content: The UTF-8 text content to write.

    Raises:
        NativeError: If the write fails (``io_error``).
        RuntimeError: If called off-device.
    """
    await send_native_request("storage", "write", {"name": name, "content": content})


async def read_file(name: str) -> str:
    """Read text from an app-private file.

    Args:
        name: The file name (relative to the app's private files directory).

    Returns:
        The file's UTF-8 text content.

    Raises:
        NativeError: If the file does not exist (``not_found``) or the read fails
            (``io_error``).
        RuntimeError: If called off-device.
    """
    data = await send_native_request("storage", "read", {"name": name})
    return str(data.get("content", ""))


async def delete_file(name: str) -> None:
    """Delete an app-private file.

    Args:
        name: The file name (relative to the app's private files directory).

    Raises:
        NativeError: If the file does not exist (``not_found``).
        RuntimeError: If called off-device.
    """
    await send_native_request("storage", "delete", {"name": name})


async def list_files() -> list[str]:
    """List the names of files in the app's private files directory.

    Returns:
        The file names, or ``[]`` when the directory is empty.

    Raises:
        RuntimeError: If called off-device.
    """
    data = await send_native_request("storage", "list", {})
    files = data.get("files", [])
    if not isinstance(files, list):
        return []
    return [str(name) for name in cast("list[Any]", files)]
