"""Unit tests for per-agent adb-server isolation helpers.

These pin the seam that lets parallel agents each drive a PRIVATE adb server
(``ANDROID_ADB_SERVER_PORT``) instead of contending on — and wedging — the shared
default 5037 server: deriving the current port from the environment, allocating a
free private port, and building the pinned environment mapping.
"""

from __future__ import annotations

import socket

import pytest

from tempestroid.testing import adb_server


def test_current_port_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset ``ANDROID_ADB_SERVER_PORT`` reports the shared default (``None``)."""
    monkeypatch.delenv("ANDROID_ADB_SERVER_PORT", raising=False)
    assert adb_server.current_adb_server_port() is None


def test_current_port_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A numeric ``ANDROID_ADB_SERVER_PORT`` is parsed to an int."""
    monkeypatch.setenv("ANDROID_ADB_SERVER_PORT", "5141")
    assert adb_server.current_adb_server_port() == 5141


def test_current_port_none_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-numeric value is treated as unset, not a crash."""
    monkeypatch.setenv("ANDROID_ADB_SERVER_PORT", "not-a-port")
    assert adb_server.current_adb_server_port() is None


def test_adb_server_env_sets_var() -> None:
    """``adb_server_env(port)`` injects the pinned port into a fresh env copy."""
    env = adb_server.adb_server_env(5142, base={"PATH": "/bin"})
    assert env["ANDROID_ADB_SERVER_PORT"] == "5142"
    assert env["PATH"] == "/bin"


def test_adb_server_env_none_leaves_base_untouched() -> None:
    """``port=None`` returns the base env without the isolation var."""
    env = adb_server.adb_server_env(None, base={"PATH": "/bin"})
    assert "ANDROID_ADB_SERVER_PORT" not in env
    assert env == {"PATH": "/bin"}


def test_allocate_prefers_a_free_preferred_port() -> None:
    """A free preferred port is returned verbatim (deterministic per-agent choice)."""
    # Find a definitely-free port by binding then releasing it.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()
    assert adb_server.allocate_adb_server_port(free_port) == free_port


def test_allocate_scans_when_preferred_busy() -> None:
    """A busy preferred port forces a scan that returns a different free port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind inside the per-agent band so the preferred port is genuinely occupied.
    listener.bind(("127.0.0.1", 0))
    busy = listener.getsockname()[1]
    listener.listen(1)
    try:
        chosen = adb_server.allocate_adb_server_port(busy)
        assert chosen != busy
        assert adb_server._AGENT_PORT_BASE <= chosen < adb_server._AGENT_PORT_CEILING  # pyright: ignore[reportPrivateUsage]
    finally:
        listener.close()


def test_allocate_scans_band_when_no_preference() -> None:
    """With no preference a port in the documented private band is returned."""
    port = adb_server.allocate_adb_server_port()
    assert adb_server._AGENT_PORT_BASE <= port < adb_server._AGENT_PORT_CEILING  # pyright: ignore[reportPrivateUsage]


def test_band_is_clear_of_shared_and_emulator_ports() -> None:
    """The private band sits above 5037 and below the emulator console band (5554)."""
    assert adb_server._AGENT_PORT_BASE > adb_server.DEFAULT_ADB_SERVER_PORT  # pyright: ignore[reportPrivateUsage]
    assert adb_server._AGENT_PORT_CEILING <= 5554  # pyright: ignore[reportPrivateUsage]
