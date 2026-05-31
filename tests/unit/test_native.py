"""Tests for native capability dispatch (phase B6)."""

from __future__ import annotations

import json
import sys
import types

import pytest

from tempestroid import notify
from tempestroid.native import native_command


def test_native_command_envelope() -> None:
    """``native_command`` builds the tagged envelope the host routes on."""
    cmd = native_command("notifications", "notify", {"title": "hi", "body": "yo"})
    assert cmd == {
        "kind": "native",
        "module": "notifications",
        "action": "notify",
        "args": {"title": "hi", "body": "yo"},
    }


def test_notify_sends_native_command() -> None:
    """``notify`` ships a notifications/notify command over the native host."""
    host = types.ModuleType("_tempest_host")
    sent: list[str] = []
    host.send_to_host = lambda message: sent.append(message)  # type: ignore[attr-defined]
    host.set_event_sink = lambda cb: None  # type: ignore[attr-defined]
    sys.modules["_tempest_host"] = host
    try:
        notify("Title", "Body")
    finally:
        del sys.modules["_tempest_host"]

    assert len(sent) == 1
    message = json.loads(sent[0])
    assert message["kind"] == "native"
    assert message["module"] == "notifications"
    assert message["action"] == "notify"
    assert message["args"] == {"title": "Title", "body": "Body"}


def test_notify_raises_off_device() -> None:
    """Calling ``notify`` off-device fails clearly (no native host)."""
    sys.modules.pop("_tempest_host", None)
    with pytest.raises(RuntimeError, match="_tempest_host is unavailable"):
        notify("x")
