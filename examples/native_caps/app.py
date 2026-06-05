"""Native-capabilities gallery (F2 device verification — no-config group).

Exercises the native capabilities that need no extra hardware or external config,
so they can be verified on a connected device straight away:

* **clipboard** — ``set_text`` / ``get_text`` (request/response round-trip).
* **storage** — ``write_file`` / ``read_file`` / ``list_files`` (app-scoped files).
* **database** — SQLite ``execute`` (create + insert + select).
* **secure_storage** — ``set_secret`` / ``get_secret`` (Keystore-backed).
* **system** — ``set_status_bar`` / ``keep_awake`` (fire-and-forget UI/system).

Each button runs one capability and writes the typed result (or a
``NativeError`` / ``(device only)`` note) into the on-screen log, so the device
screenshot is the evidence. The module is renderer-agnostic — ``run_qt`` is
imported lazily — so it also opens in the Qt simulator (where the device-only
capabilities report ``(device only)`` instead of raising).

Run on a device::

    uv run tempest serve examples/native_caps/app.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)
from tempestroid.native import (
    NativeError,
    execute,
    get_secret,
    get_text,
    keep_awake,
    list_files,
    on_device,
    read_file,
    set_secret,
    set_status_bar,
    set_text,
    write_file,
)
from tempestroid.native.system import StatusBarStyle


def _empty_log() -> list[str]:
    """Provide a fresh, typed empty log list for the dataclass default.

    Returns:
        A new empty list of result lines.
    """
    return []


@dataclass
class State:
    """The gallery's mutable state.

    Attributes:
        log: The most recent capability results, newest first.
    """

    log: list[str] = field(default_factory=_empty_log)


def make_state() -> State:
    """Build a fresh initial state.

    Returns:
        A new gallery state with an empty log.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Build the gallery UI.

    Args:
        app: The running app.

    Returns:
        The gallery screen.
    """

    def _record(line: str) -> None:
        """Prepend a result line to the on-screen log."""
        app.set_state(lambda s: s.log.insert(0, line))

    async def clipboard_roundtrip() -> None:
        """Set then read back the clipboard."""
        if not on_device():
            _record("clipboard: (device only)")
            return
        try:
            set_text("tempestroid ✓")
            value = await get_text()
            _record(f"clipboard: {value!r}")
        except NativeError as exc:
            _record(f"clipboard: error {exc}")

    async def storage_roundtrip() -> None:
        """Write, read back, and list app-scoped files."""
        if not on_device():
            _record("storage: (device only)")
            return
        try:
            await write_file("note.txt", "hello from python")
            content = await read_file("note.txt")
            files = await list_files()
            _record(f"storage: read={content!r} files={files}")
        except NativeError as exc:
            _record(f"storage: error {exc}")

    async def database_roundtrip() -> None:
        """Create a table, insert a row, and select it back via SQLite."""
        try:
            await execute("CREATE TABLE IF NOT EXISTS t (id INTEGER, name TEXT)")
            await execute("INSERT INTO t (id, name) VALUES (?, ?)", (1, "ada"))
            result = await execute("SELECT COUNT(*) FROM t")
            _record(f"database: rows={result.rows}")
        except NativeError as exc:
            _record(f"database: error {exc}")

    async def secret_roundtrip() -> None:
        """Store then read back a secret."""
        if not on_device():
            _record("secret: (device only)")
            return
        try:
            set_secret("token", "s3cr3t")
            value = await get_secret("token")
            _record(f"secret: {value!r}")
        except NativeError as exc:
            _record(f"secret: error {exc}")

    def system_calls() -> None:
        """Run fire-and-forget system tweaks (status bar + keep awake)."""
        if not on_device():
            _record("system: (device only)")
            return
        try:
            set_status_bar(style=StatusBarStyle.LIGHT, color="#0b3d2e")
            keep_awake(True)
            _record("system: status bar + keep_awake applied")
        except NativeError as exc:
            _record(f"system: error {exc}")

    def _btn(label: str, handler: object, key: str) -> Button:
        """Build a styled gallery button."""
        return Button(
            label=label,
            on_click=handler,  # type: ignore[arg-type]
            key=key,
            style=Style(
                background=Color.from_hex("#2563eb"),
                color=Color.from_hex("#ffffff"),
                padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
                radius=8.0,
            ),
        )

    log_lines: list[Widget] = [
        Text(
            content=line,
            style=Style(color=Color.from_hex("#9ca3af"), font_size=13.0),
            key=f"log-{index}",
        )
        for index, line in enumerate(app.state.log[:12])
    ]

    return Column(
        style=Style(
            gap=12.0,
            padding=Edge.all(20.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content="Native capabilities",
                style=Style(
                    color=Color.from_hex("#f9fafb"),
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="title",
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    _btn("Clipboard", clipboard_roundtrip, "clip"),
                    _btn("Storage", storage_roundtrip, "store"),
                    _btn("Database", database_roundtrip, "db"),
                ],
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    _btn("Secret", secret_roundtrip, "secret"),
                    _btn("System", system_calls, "system"),
                ],
            ),
            Column(style=Style(gap=4.0), children=log_lines, key="log"),
        ],
    )


def main() -> int:
    """Run the gallery in the Qt simulator.

    Returns:
        The process exit code.
    """
    from tempestroid.renderers.qt import run_qt

    return run_qt(make_state(), view, title="tempestroid — native caps")


if __name__ == "__main__":
    raise SystemExit(main())
