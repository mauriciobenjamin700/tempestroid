"""Tests for native capability dispatch (phase B6+)."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from tempestroid import notify
from tempestroid.native import (
    AudioClip,
    BluetoothDevice,
    CameraFacing,
    NativeError,
    Photo,
    Position,
    Video,
    VideoQuality,
    delete_file,
    get_position,
    get_text,
    list_files,
    native_command,
    native_request,
    open_url,
    play_sound,
    read_file,
    record_audio,
    record_video,
    resolve_native_result,
    scan,
    set_text,
    share,
    share_to_whatsapp,
    stop_sound,
    take_photo,
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
