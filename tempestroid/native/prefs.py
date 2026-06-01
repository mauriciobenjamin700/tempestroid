"""Native key-value preferences capability (phase E8).

On the device the Kotlin ``PrefsModule`` drives ``SharedPreferences`` over the
request/response (get/get_all) and fire-and-forget (set/delete) shapes. On the
Qt simulator the store is *real*: preferences persist to a JSON file under the
preferences directory (``~/.tempestroid/prefs.json`` by default), so a desktop
app behaves the same across restarts without a device.

Tests override the desktop store location via :func:`set_prefs_path` (pointed at
a ``tmp_path``) to stay isolated and avoid touching the user's home directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tempestroid.native.dispatch import on_device, send_native, send_native_request

__all__ = [
    "get_pref",
    "set_pref",
    "delete_pref",
    "get_all_prefs",
    "set_prefs_path",
]

#: The desktop JSON store path; ``None`` means the default under the home dir.
_prefs_path: Path | None = None


def set_prefs_path(path: Path | None) -> None:
    """Override the desktop preferences-file location (test isolation).

    Args:
        path: The JSON file to read/write on the Qt simulator, or ``None`` to
            restore the default ``~/.tempestroid/prefs.json``.
    """
    global _prefs_path
    _prefs_path = path


def _store_path() -> Path:
    """Resolve the desktop preferences-file path, creating its parent dir.

    Returns:
        The JSON store path (parent directory ensured to exist).
    """
    path = _prefs_path or (Path.home() / ".tempestroid" / "prefs.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_store() -> dict[str, Any]:
    """Read the desktop preferences store.

    Returns:
        The decoded preferences mapping (empty when the file is absent/invalid).
    """
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, dict):
        return cast("dict[str, Any]", data)
    return {}


def _write_store(store: dict[str, Any]) -> None:
    """Write the desktop preferences store.

    Args:
        store: The full preferences mapping to persist.
    """
    _store_path().write_text(json.dumps(store), encoding="utf-8")


async def get_pref(key: str, default: Any = None) -> Any:  # noqa: ANN401 — a JSON-able preference value is arbitrary
    """Read a preference value.

    Args:
        key: The preference key.
        default: The value to return when the key is absent.

    Returns:
        The stored value, or ``default`` when the key is absent.
    """
    if not on_device():
        return _read_store().get(key, default)
    data = await send_native_request("prefs", "get", {"key": key})
    return data.get("value", default) if "value" in data else default


def set_pref(key: str, value: Any) -> None:  # noqa: ANN401 — a JSON-able preference value is arbitrary
    """Write a preference value.

    Args:
        key: The preference key.
        value: The JSON-able value to store.
    """
    if not on_device():
        store = _read_store()
        store[key] = value
        _write_store(store)
        return
    send_native("prefs", "set", {"key": key, "value": value})


def delete_pref(key: str) -> None:
    """Delete a preference.

    Args:
        key: The preference key to remove (a no-op when absent).
    """
    if not on_device():
        store = _read_store()
        store.pop(key, None)
        _write_store(store)
        return
    send_native("prefs", "delete", {"key": key})


async def get_all_prefs() -> dict[str, Any]:
    """Read every stored preference.

    Returns:
        A mapping of all preference keys to their values (empty when none).
    """
    if not on_device():
        return _read_store()
    data = await send_native_request("prefs", "get_all", {})
    values: Any = data.get("values", {})
    if isinstance(values, dict):
        return cast("dict[str, Any]", values)
    return {}
