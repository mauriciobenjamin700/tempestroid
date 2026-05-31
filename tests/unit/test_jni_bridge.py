"""Tests for the device JNI transport (phase B3, Python half).

The native ``_tempest_host`` module exists only inside the Android app, so these
tests stub it in ``sys.modules`` to exercise :class:`JniBridge` and the event
sink wiring without a device.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import pytest

from tempestroid.bridge.jni import JniBridge


def _fake_host() -> types.ModuleType:
    """Build a stand-in ``_tempest_host`` module recording its calls.

    Returns:
        A module exposing ``send_to_host`` / ``set_event_sink`` plus the captured
        ``sent`` list and ``sink`` reference.
    """
    module = types.ModuleType("_tempest_host")
    sent: list[str] = []
    module.sent = sent  # type: ignore[attr-defined]
    module.sink = None  # type: ignore[attr-defined]
    module.send_to_host = lambda message: sent.append(message)  # type: ignore[attr-defined]

    def _set_sink(cb: Any) -> None:
        module.sink = cb  # type: ignore[attr-defined]

    module.set_event_sink = _set_sink  # type: ignore[attr-defined]
    return module


def test_jni_bridge_raises_off_device() -> None:
    """Constructing a ``JniBridge`` fails clearly when the native module is absent."""
    sys.modules.pop("_tempest_host", None)
    with pytest.raises(RuntimeError, match="_tempest_host is unavailable"):
        JniBridge()


async def test_jni_bridge_sends_json() -> None:
    """``JniBridge.send`` JSON-encodes and forwards to ``send_to_host``."""
    host = _fake_host()
    sys.modules["_tempest_host"] = host
    try:
        bridge = JniBridge()
        await bridge.send({"kind": "mount", "root": {"type": "Text"}})
    finally:
        del sys.modules["_tempest_host"]

    assert len(host.sent) == 1  # type: ignore[attr-defined]
    decoded = json.loads(host.sent[0])  # type: ignore[attr-defined]
    assert decoded == {"kind": "mount", "root": {"type": "Text"}}
