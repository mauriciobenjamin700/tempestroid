"""Tests for native capability dispatch (phase B6+)."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from tempest_core.widgets.events import (
    AppState,
    ConnectivityState,
    SensorType,
)

from tempestroid import notify
from tempestroid.native import (
    AudioClip,
    BiometricResult,
    BluetoothDevice,
    CameraFacing,
    ImpactStyle,
    NativeError,
    PermissionStatus,
    Photo,
    Position,
    QueryResult,
    Video,
    VideoQuality,
    authenticate,
    cancel_task,
    check_permission,
    delete_file,
    delete_pref,
    delete_secret,
    dispatch_connectivity_event,
    dispatch_lifecycle_event,
    dispatch_sensor_event,
    execute,
    execute_many,
    get_all_prefs,
    get_brightness,
    get_position,
    get_pref,
    get_secret,
    get_text,
    impact,
    keep_awake,
    list_files,
    native_command,
    native_request,
    on_app_state_change,
    on_background_task,
    open_url,
    play_sound,
    read_file,
    record_audio,
    record_video,
    register_push,
    request_permission,
    resolve_native_result,
    scan,
    schedule_notification,
    schedule_task,
    set_brightness,
    set_database_path,
    set_pref,
    set_prefs_path,
    set_secret,
    set_status_bar,
    set_text,
    share,
    share_to_whatsapp,
    start_sensor,
    stop_sound,
    take_photo,
    vibrate,
    write_file,
)


class _FakeHost:
    """In-memory stand-in for ``_tempest_host`` that auto-answers requests.

    Each serialized message handed to :meth:`send_to_host` is recorded; if it
    carries a ``request_id`` the next queued response is resolved against it,
    simulating the device replying over the event channel.
    """

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        """Initialize the fake host.

        Args:
            responses: Result envelopes to hand back, one per request, in order.
        """
        self.sent: list[dict[str, Any]] = []
        self._responses: Iterator[dict[str, Any]] = iter(responses or [])

    def send_to_host(self, message_json: str) -> None:
        """Record a sent message and auto-resolve if it is a request."""
        message: dict[str, Any] = json.loads(message_json)
        self.sent.append(message)
        request_id = message.get("request_id")
        if request_id is not None:
            resolve_native_result(request_id, next(self._responses))

    def set_event_sink(self, sink: Callable[[str, str], None]) -> None:
        """Accept (and ignore) an event sink registration."""


@pytest.fixture
def install_host() -> Iterator[Callable[[list[dict[str, Any]] | None], _FakeHost]]:
    """Install a :class:`_FakeHost` as ``_tempest_host`` for the test's duration."""
    installed: list[str] = []

    def _install(responses: list[dict[str, Any]] | None = None) -> _FakeHost:
        host = _FakeHost(responses)
        module = types.ModuleType("_tempest_host")
        module.send_to_host = host.send_to_host  # type: ignore[attr-defined]
        module.set_event_sink = host.set_event_sink  # type: ignore[attr-defined]
        sys.modules["_tempest_host"] = module
        installed.append("_tempest_host")
        return host

    yield _install
    for name in installed:
        sys.modules.pop(name, None)


# --- envelope builders (pure) ------------------------------------------------


def test_native_command_envelope() -> None:
    """``native_command`` builds the fire-and-forget envelope."""
    cmd = native_command("notifications", "notify", {"title": "hi", "body": "yo"})
    assert cmd == {
        "kind": "native",
        "module": "notifications",
        "action": "notify",
        "args": {"title": "hi", "body": "yo"},
    }


def test_native_request_envelope_carries_request_id() -> None:
    """``native_request`` tags the envelope with a correlation id."""
    cmd = native_request("geolocation", "get_position", {"high_accuracy": True}, "7")
    assert cmd == {
        "kind": "native",
        "module": "geolocation",
        "action": "get_position",
        "args": {"high_accuracy": True},
        "request_id": "7",
    }


# --- fire-and-forget capabilities --------------------------------------------


def test_notify_sends_native_command(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``notify`` ships a notifications/notify command over the native host."""
    host = install_host(None)
    notify("Title", "Body")
    assert len(host.sent) == 1
    assert host.sent[0] == {
        "kind": "native",
        "module": "notifications",
        "action": "notify",
        "args": {"title": "Title", "body": "Body"},
    }


def test_share_capabilities_send_commands(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``share`` / ``share_to_whatsapp`` / ``open_url`` ship one-way commands."""
    host = install_host(None)
    share(text="hello", url="https://x.dev", title="Pick")
    share_to_whatsapp(text="hi", phone="5511999999999")
    open_url("https://x.dev")
    set_text("clip")
    actions = [(m["module"], m["action"]) for m in host.sent]
    assert actions == [
        ("share", "share"),
        ("share", "whatsapp"),
        ("share", "open_url"),
        ("clipboard", "set"),
    ]
    assert "request_id" not in host.sent[0]


def test_notify_raises_off_device() -> None:
    """Calling ``notify`` off-device fails clearly (no native host)."""
    sys.modules.pop("_tempest_host", None)
    with pytest.raises(RuntimeError, match="_tempest_host is unavailable"):
        notify("x")


# --- request/response infrastructure -----------------------------------------


def test_resolve_unknown_request_returns_false() -> None:
    """Resolving an unknown/settled request id is a no-op returning ``False``."""
    assert resolve_native_result("does-not-exist", {"ok": True}) is False


def test_native_error_carries_code(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """A failing result raises ``NativeError`` carrying the host's code."""
    install_host([{"ok": False, "error": "permission_denied", "message": "denied"}])

    async def run() -> None:
        with pytest.raises(NativeError) as info:
            await get_position()
        assert info.value.code == "permission_denied"

    asyncio.run(run())


# --- request/response capabilities -------------------------------------------


def test_get_position_parses_fix(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``get_position`` returns the host's fix as a typed ``Position``."""
    host = install_host(
        [{"ok": True, "data": {"latitude": -23.5, "longitude": -46.6, "accuracy": 8.0}}]
    )

    async def run() -> Position:
        return await get_position(high_accuracy=True)

    position = asyncio.run(run())
    assert position == Position(latitude=-23.5, longitude=-46.6, accuracy=8.0)
    assert host.sent[0]["module"] == "geolocation"
    assert host.sent[0]["args"] == {"high_accuracy": True}


def test_take_photo_parses_result(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``take_photo`` returns the saved path as a typed ``Photo``."""
    install_host([{"ok": True, "data": {"path": "/data/x.jpg", "width": 100}}])

    async def run() -> Photo:
        return await take_photo()

    photo = asyncio.run(run())
    assert photo == Photo(path="/data/x.jpg", width=100)


def test_take_photo_forwards_params(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``take_photo`` forwards the camera/size params in the envelope args."""
    host = install_host([{"ok": True, "data": {"path": "/data/x.jpg"}}])

    async def run() -> Photo:
        return await take_photo(
            camera=CameraFacing.FRONT, max_width=640, max_height=480
        )

    asyncio.run(run())
    assert host.sent[0]["module"] == "camera"
    assert host.sent[0]["action"] == "take_photo"
    assert host.sent[0]["args"] == {
        "camera": "front",
        "max_width": 640,
        "max_height": 480,
    }


def test_record_video_parses_result_and_forwards_params(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``record_video`` returns a typed ``Video`` and forwards its params."""
    host = install_host(
        [{"ok": True, "data": {"path": "/data/v.mp4", "duration_ms": 4200}}]
    )

    async def run() -> Video:
        return await record_video(
            camera=CameraFacing.BACK, max_duration_s=30, quality=VideoQuality.LOW
        )

    video = asyncio.run(run())
    assert video == Video(path="/data/v.mp4", duration_ms=4200)
    assert host.sent[0]["action"] == "record_video"
    assert host.sent[0]["args"] == {
        "camera": "back",
        "max_duration_s": 30,
        "quality": "low",
    }


def test_record_audio_parses_clip(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``record_audio`` (microphone) returns a typed ``AudioClip``."""
    host = install_host(
        [{"ok": True, "data": {"path": "/data/a.m4a", "duration_ms": 1500}}]
    )

    async def run() -> AudioClip:
        return await record_audio(max_duration_s=5)

    clip = asyncio.run(run())
    assert clip == AudioClip(path="/data/a.m4a", duration_ms=1500)
    assert host.sent[0]["module"] == "audio"
    assert host.sent[0]["args"] == {"max_duration_s": 5}


def test_play_and_stop_sound_send_commands(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``play_sound`` / ``stop_sound`` drive the speaker via the audio module."""
    host = install_host([{"ok": True, "data": {}}, {"ok": True, "data": {}}])

    async def run() -> None:
        await play_sound("/data/a.m4a", volume=0.5)
        await stop_sound()

    asyncio.run(run())
    assert host.sent[0]["action"] == "play_sound"
    assert host.sent[0]["args"] == {"src": "/data/a.m4a", "volume": 0.5}
    assert host.sent[1]["action"] == "stop_sound"


def test_storage_round_trip(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """Storage write/read/list/delete each ship the right action and parse back."""
    host = install_host(
        [
            {"ok": True, "data": {}},
            {"ok": True, "data": {"content": "hello"}},
            {"ok": True, "data": {"files": ["a.txt", "b.txt"]}},
            {"ok": True, "data": {}},
        ]
    )

    async def run() -> tuple[str, list[str]]:
        await write_file("a.txt", "hello")
        content = await read_file("a.txt")
        files = await list_files()
        await delete_file("a.txt")
        return content, files

    content, files = asyncio.run(run())
    assert content == "hello"
    assert files == ["a.txt", "b.txt"]
    assert [m["action"] for m in host.sent] == ["write", "read", "list", "delete"]


def test_read_file_missing_raises_not_found(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """A missing file surfaces as ``NativeError('not_found')`` (single-resource)."""
    install_host([{"ok": False, "error": "not_found"}])

    async def run() -> None:
        with pytest.raises(NativeError) as info:
            await read_file("missing.txt")
        assert info.value.code == "not_found"

    asyncio.run(run())


def test_list_files_empty_returns_empty_list(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """An empty storage dir returns ``[]`` (collection convention, never raises)."""
    install_host([{"ok": True, "data": {}}])

    async def run() -> list[str]:
        return await list_files()

    assert asyncio.run(run()) == []


def test_clipboard_get_text(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``get_text`` returns the clipboard text."""
    install_host([{"ok": True, "data": {"text": "copied"}}])

    async def run() -> str:
        return await get_text()

    assert asyncio.run(run()) == "copied"


def test_bluetooth_scan_parses_devices(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``scan`` returns discovered devices; empty discovery returns ``[]``."""
    install_host(
        [
            {
                "ok": True,
                "data": {
                    "devices": [
                        {"address": "AA:BB", "name": "Speaker", "rssi": -60},
                        {"address": "CC:DD"},
                    ]
                },
            }
        ]
    )

    async def run() -> list[BluetoothDevice]:
        return await scan(timeout=2.0)

    devices = asyncio.run(run())
    assert devices == [
        BluetoothDevice(address="AA:BB", name="Speaker", rssi=-60),
        BluetoothDevice(address="CC:DD"),
    ]


# === phase E8: platform / system ============================================


@pytest.fixture
def off_device() -> Iterator[None]:
    """Ensure ``_tempest_host`` is absent for the test (simulate the desktop)."""
    saved = sys.modules.pop("_tempest_host", None)
    yield
    if saved is not None:
        sys.modules["_tempest_host"] = saved


# --- haptics (fire-and-forget) ----------------------------------------------


def test_vibrate_sends_fire_and_forget(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``vibrate`` ships a haptics/vibrate command with no request_id."""
    host = install_host(None)
    vibrate(120)
    assert host.sent[0] == {
        "kind": "native",
        "module": "haptics",
        "action": "vibrate",
        "args": {"duration_ms": 120},
    }
    assert "request_id" not in host.sent[0]


def test_impact_sends_style(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``impact`` ships the intensity style on the haptics module."""
    host = install_host(None)
    impact(ImpactStyle.HEAVY)
    assert host.sent[0]["module"] == "haptics"
    assert host.sent[0]["action"] == "impact"
    assert host.sent[0]["args"] == {"style": "heavy"}


# --- system (mixed: set=ff, get=req/resp) -----------------------------------


def test_get_brightness_envelope_and_parse(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``get_brightness`` sends a system/get_brightness request and parses it."""
    host = install_host([{"ok": True, "data": {"value": 0.7}}])

    async def run() -> float:
        return await get_brightness()

    value = asyncio.run(run())
    assert abs(value - 0.7) < 1e-9
    assert host.sent[0]["module"] == "system"
    assert host.sent[0]["action"] == "get_brightness"
    assert "request_id" in host.sent[0]


def test_system_setters_send_commands(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """The system setters ship fire-and-forget commands."""
    host = install_host(None)
    set_status_bar(hidden=True, color="#101010")
    set_brightness(0.5)
    keep_awake(True)
    actions = [(m["module"], m["action"]) for m in host.sent]
    assert actions == [
        ("system", "set_status_bar"),
        ("system", "set_brightness"),
        ("system", "keep_awake"),
    ]
    assert host.sent[0]["args"]["hidden"] is True
    assert host.sent[1]["args"] == {"value": 0.5}


# --- sensor / lifecycle / connectivity streams (reserved tokens) ------------


def test_sensor_stream_registers_and_dispatches(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``start_sensor`` ships a start command and ``_on_sensor`` fans out samples.

    Simulates the host pushing a sample over the reserved
    ``"__sensor__:accelerometer"`` token (routed in the bridge to ``_on_sensor``).
    """
    host = install_host(None)
    received: list[list[float]] = []

    stop = start_sensor(
        SensorType.ACCELEROMETER, lambda e: received.append(e.values), rate_ms=50
    )
    assert host.sent[0] == {
        "kind": "native",
        "module": "sensors",
        "action": "start",
        "args": {"sensor": "accelerometer", "rate_ms": 50},
    }

    # Host pushes a sample (token "__sensor__:accelerometer" routes here).
    dispatch_sensor_event(
        "accelerometer", {"values": [0.0, 9.8, 0.1], "timestamp_ms": 7}
    )
    assert received == [[0.0, 9.8, 0.1]]

    # Unregister: the callback no longer fires and a stop command is sent.
    stop()
    assert host.sent[-1] == {
        "kind": "native",
        "module": "sensors",
        "action": "stop",
        "args": {"sensor": "accelerometer"},
    }
    dispatch_sensor_event("accelerometer", {"values": [1.0]})
    assert received == [[0.0, 9.8, 0.1]]


def test_lifecycle_registry_and_unregister() -> None:
    """``on_app_state_change`` registers a callback ``_on_lifecycle`` fans out to."""
    states: list[AppState] = []
    unregister = on_app_state_change(lambda e: states.append(e.state))

    dispatch_lifecycle_event({"state": "foreground"})
    dispatch_lifecycle_event({"state": "background"})
    assert states == [AppState.FOREGROUND, AppState.BACKGROUND]

    unregister()
    dispatch_lifecycle_event({"state": "foreground"})
    assert states == [AppState.FOREGROUND, AppState.BACKGROUND]


def test_connectivity_stream_dispatch(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``on_connectivity_change`` registers a callback ``_on_connectivity`` fans to."""
    from tempestroid.native import on_connectivity_change

    install_host(None)
    seen: list[ConnectivityState] = []
    unregister = on_connectivity_change(lambda e: seen.append(e.state))

    dispatch_connectivity_event({"state": "wifi"})
    assert seen == [ConnectivityState.WIFI]

    unregister()
    dispatch_connectivity_event({"state": "disconnected"})
    assert seen == [ConnectivityState.WIFI]


# --- permissions / biometrics (Qt stubs) ------------------------------------


def test_request_permission_granted_off_device(off_device: None) -> None:
    """Off-device (Qt), permission requests are granted immediately."""

    async def run() -> PermissionStatus:
        result = await request_permission("android.permission.CAMERA")
        return result.status

    assert asyncio.run(run()) == PermissionStatus.GRANTED


def test_check_permission_granted_off_device(off_device: None) -> None:
    """Off-device (Qt), permission checks report granted."""

    async def run() -> PermissionStatus:
        return (await check_permission("android.permission.CAMERA")).status

    assert asyncio.run(run()) == PermissionStatus.GRANTED


def test_request_permission_parses_device_result(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """On device, the host's status is parsed into a typed PermissionResult."""
    host = install_host([{"ok": True, "data": {"status": "denied"}}])

    async def run() -> PermissionStatus:
        return (await request_permission("android.permission.CAMERA")).status

    assert asyncio.run(run()) == PermissionStatus.DENIED
    assert host.sent[0]["module"] == "permissions"


def test_authenticate_device_only_off_device(off_device: None) -> None:
    """Off-device (Qt), biometrics raise NativeError('device_only')."""

    async def run() -> None:
        with pytest.raises(NativeError) as info:
            await authenticate("Unlock")
        assert info.value.code == "device_only"

    asyncio.run(run())


def test_authenticate_parses_device_result(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """On device, ``authenticate`` parses the host BiometricResult."""
    install_host([{"ok": True, "data": {"authenticated": True}}])

    async def run() -> BiometricResult:
        return await authenticate("Unlock")

    result = asyncio.run(run())
    assert result == BiometricResult(authenticated=True)


# --- secure storage (Qt = device_only) --------------------------------------


def test_secure_storage_device_only_off_device(off_device: None) -> None:
    """Off-device (Qt), secure storage raises NativeError('device_only')."""

    async def run() -> None:
        with pytest.raises(NativeError) as info:
            await get_secret("token")
        assert info.value.code == "device_only"

    asyncio.run(run())
    with pytest.raises(NativeError):
        set_secret("token", "x")
    with pytest.raises(NativeError):
        delete_secret("token")


# --- prefs (Qt = real JSON store via tmp_path) ------------------------------


@pytest.fixture
def prefs_store(tmp_path: Path) -> Iterator[Path]:
    """Point the desktop prefs store at an isolated tmp file."""
    store = tmp_path / "prefs.json"
    set_prefs_path(store)
    sys.modules.pop("_tempest_host", None)
    yield store
    set_prefs_path(None)


def test_prefs_round_trip_real_store(prefs_store: Path) -> None:
    """Off-device prefs persist to JSON: set, read back, list, delete."""

    async def run() -> tuple[Any, dict[str, Any], Any]:
        set_pref("name", "ada")
        set_pref("count", 3)
        name = await get_pref("name")
        allp = await get_all_prefs()
        delete_pref("name")
        after = await get_pref("name", "missing")
        return name, allp, after

    name, allp, after = asyncio.run(run())
    assert name == "ada"
    assert allp == {"name": "ada", "count": 3}
    assert after == "missing"
    # The store is a real JSON file holding the surviving key.
    assert json.loads(prefs_store.read_text()) == {"count": 3}


def test_get_pref_default_when_absent(prefs_store: Path) -> None:
    """A missing pref returns the supplied default."""

    async def run() -> Any:
        return await get_pref("nope", default=42)

    assert asyncio.run(run()) == 42


# --- database (Qt = real sqlite3 via tmp_path) ------------------------------


@pytest.fixture
def db_store(tmp_path: Path) -> Iterator[Path]:
    """Point the desktop SQLite db at an isolated tmp file."""
    db = tmp_path / "app.db"
    set_database_path(db)
    sys.modules.pop("_tempest_host", None)
    yield db
    set_database_path(None)


def test_database_round_trip_real_sqlite(db_store: Path) -> None:
    """Off-device database runs real SQL: create, insert-many, select back."""

    async def run() -> QueryResult:
        await execute("CREATE TABLE todos (id INTEGER PRIMARY KEY, title TEXT)")
        await execute_many(
            "INSERT INTO todos (title) VALUES (?)", [("a",), ("b",), ("c",)]
        )
        return await execute("SELECT title FROM todos ORDER BY id")

    result = asyncio.run(run())
    assert result.columns == ["title"]
    assert result.rows == [["a"], ["b"], ["c"]]
    assert db_store.exists()


def test_database_select_empty_returns_empty_rows(db_store: Path) -> None:
    """A SELECT matching nothing returns empty rows (never None)."""

    async def run() -> QueryResult:
        await execute("CREATE TABLE t (id INTEGER)")
        return await execute("SELECT id FROM t")

    result = asyncio.run(run())
    assert result.rows == []
    assert result.columns == ["id"]


# --- push / background ------------------------------------------------------


def test_register_push_device_only_off_device(off_device: None) -> None:
    """Off-device (Qt), push registration raises NativeError('device_only')."""

    async def run() -> None:
        with pytest.raises(NativeError) as info:
            await register_push()
        assert info.value.code == "device_only"

    asyncio.run(run())


def test_register_push_parses_token(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """On device, ``register_push`` returns the host's FCM token."""
    install_host([{"ok": True, "data": {"token": "fcm-abc"}}])

    async def run() -> str:
        return (await register_push()).token

    assert asyncio.run(run()) == "fcm-abc"


def test_schedule_notification_envelope(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``schedule_notification`` ships a fire-and-forget push command."""
    host = install_host(None)
    schedule_notification("Hi", "Body", 60.0)
    assert host.sent[0] == {
        "kind": "native",
        "module": "push",
        "action": "schedule_notification",
        "args": {"title": "Hi", "body": "Body", "delay_s": 60.0},
    }


def test_background_task_envelopes(
    install_host: Callable[[list[dict[str, Any]] | None], _FakeHost],
) -> None:
    """``schedule_task`` / ``cancel_task`` ship background commands."""
    host = install_host(None)
    schedule_task("sync", interval_s=900.0)
    cancel_task("sync")
    assert host.sent[0] == {
        "kind": "native",
        "module": "background",
        "action": "schedule",
        "args": {"name": "sync", "interval_s": 900.0},
    }
    assert host.sent[1]["action"] == "cancel"
    assert host.sent[1]["args"] == {"name": "sync"}


def test_on_background_task_registry_runs_handler() -> None:
    """A fired background task runs the handler registered for its name."""
    from tempestroid.native.background import dispatch_background_task

    fired: list[str] = []
    unregister = on_background_task("sync", lambda: fired.append("sync"))
    dispatch_background_task("sync")
    assert fired == ["sync"]
    # An unrelated name fires nothing.
    dispatch_background_task("other")
    assert fired == ["sync"]
    # Unregistering stops further dispatch.
    unregister()
    dispatch_background_task("sync")
    assert fired == ["sync"]
