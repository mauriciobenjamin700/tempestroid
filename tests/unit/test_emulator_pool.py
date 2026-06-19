"""Unit tests for the F9 emulator pool (allocation logic, adb/subprocess mocked).

No emulator is started: ``adb devices`` and the ``device_loop.sh`` helper calls
are stubbed, so the tests pin the port scheme, the hardware cap, the reuse of
already-running instances, and that a teardown only stops pool-booted serials.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from tempestroid.testing import EmulatorPool
from tempestroid.testing import pool as pool_mod

#: The real ``_port_in_use`` captured before the autouse fixture stubs it, so the
#: socket-level unit test can exercise the genuine implementation.
_REAL_PORT_IN_USE = pool_mod._port_in_use  # pyright: ignore[reportPrivateUsage]


@pytest.fixture()
def stub_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub port/serial probing so a boot-path test never touches adb or sockets.

    Defaults to "nothing attached, every port free", so the boot-scheme tests
    behave deterministically regardless of any emulator actually running on the
    host. A test exercising the poisoned-port skip overrides one of these after
    requesting the fixture.

    Args:
        monkeypatch: The pytest monkeypatcher.
    """

    def no_attached(adb: str = "adb") -> set[str]:
        return set()

    def all_free(port: int) -> bool:
        return False

    monkeypatch.setattr(pool_mod, "_attached_serials", no_attached)
    monkeypatch.setattr(pool_mod, "_port_in_use", all_free)


@pytest.fixture()
def captured_helpers(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Capture every ``device_loop.sh`` helper invocation instead of running it.

    Args:
        monkeypatch: The pytest monkeypatcher.

    Returns:
        A list that fills with ``(func, *args)`` tuples per helper call.
    """
    calls: list[tuple[str, ...]] = []

    def fake_helper(self: EmulatorPool, func: str, *args: str) -> None:
        calls.append((func, *args))

    monkeypatch.setattr(EmulatorPool, "_run_helper", fake_helper)
    return calls


def _stub_running(monkeypatch: pytest.MonkeyPatch, serials: list[str]) -> None:
    """Stub :func:`running_emulators` to return ``serials``.

    Args:
        monkeypatch: The pytest monkeypatcher.
        serials: The serials to report as running.
    """
    monkeypatch.setattr(pool_mod, "running_emulators", lambda adb="adb": list(serials))


def _stub_cap(monkeypatch: pytest.MonkeyPatch, ceiling: int) -> None:
    """Stub the hardware cap to a fixed ``ceiling``.

    Args:
        monkeypatch: The pytest monkeypatcher.
        ceiling: The cap to report.
    """
    monkeypatch.setattr(pool_mod, "max_parallel_emulators", lambda: ceiling)


def test_allocate_reuses_running_first(
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
) -> None:
    """A running emulator is reused; no boot helper is invoked."""
    _stub_running(monkeypatch, ["emulator-5554"])
    _stub_cap(monkeypatch, 4)
    logs: list[str] = []
    pool = EmulatorPool(log=logs.append)

    serials = pool.allocate(1)

    assert serials == ["emulator-5554"]
    assert captured_helpers == []  # nothing booted
    assert any("reusing" in line for line in logs)


def test_allocate_boots_to_fill_with_port_scheme(
    monkeypatch: pytest.MonkeyPatch,
    captured_helpers: list[tuple[str, ...]],
    stub_ports: None,
) -> None:
    """With nothing running, instances boot at ports 5554, 5556, ... ."""
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 4)
    pool = EmulatorPool(log=lambda _line: None)

    serials = pool.allocate(2)

    assert serials == ["emulator-5554", "emulator-5556"]
    boots = [c for c in captured_helpers if c[0] == "emu_boot"]
    # emu_boot avd serial port snapshot
    assert boots[0][1:4] == ("pixel8_api34", "emulator-5554", "5554")
    assert boots[1][1:4] == ("pixel8_api34", "emulator-5556", "5556")


def test_allocate_caps_below_request_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    captured_helpers: list[tuple[str, ...]],
    stub_ports: None,
) -> None:
    """Requesting more than the hardware cap is capped, and the cap is logged."""
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 2)
    logs: list[str] = []
    pool = EmulatorPool(log=logs.append)

    serials = pool.allocate(8)

    assert len(serials) == 2
    assert any("capping" in line for line in logs)


def test_no_boot_mode_only_reuses(
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
) -> None:
    """With ``boot=False`` the pool never boots — it only reuses running ones."""
    _stub_running(monkeypatch, ["emulator-5554"])
    _stub_cap(monkeypatch, 4)
    logs: list[str] = []
    pool = EmulatorPool(boot=False, log=logs.append)

    serials = pool.allocate(3)

    assert serials == ["emulator-5554"]
    assert captured_helpers == []
    assert any("boot disabled" in line for line in logs)


def test_teardown_only_stops_booted(
    monkeypatch: pytest.MonkeyPatch,
    captured_helpers: list[tuple[str, ...]],
    stub_ports: None,
) -> None:
    """Teardown stops the instance the pool booted, not the reused one."""
    _stub_running(monkeypatch, ["emulator-5554"])
    _stub_cap(monkeypatch, 4)
    pool = EmulatorPool(log=lambda _line: None)

    pool.allocate(2)  # reuse 5554, boot 5556
    captured_helpers.clear()
    pool.teardown()

    stops = [c for c in captured_helpers if c[0] == "emu_stop"]
    assert stops == [("emu_stop", "emulator-5556")]


def test_release_reused_does_not_stop(
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
) -> None:
    """Releasing a reused serial does not stop it (the pool did not boot it)."""
    _stub_running(monkeypatch, ["emulator-5554"])
    _stub_cap(monkeypatch, 4)
    pool = EmulatorPool(log=lambda _line: None)
    pool.allocate(1)
    captured_helpers.clear()

    pool.release("emulator-5554")

    assert captured_helpers == []


def test_recycle_uses_recover_with_port(
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
) -> None:
    """Recycling a serial invokes emu_recover with the parsed console port."""
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 4)
    pool = EmulatorPool(log=lambda _line: None)

    pool.recycle("emulator-5556")

    recovers = [c for c in captured_helpers if c[0] == "emu_recover"]
    assert recovers == [("emu_recover", "pixel8_api34", "emulator-5556", "5556")]


def test_running_emulators_parses_only_emulator_serials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``running_emulators`` returns only ready ``emulator-*`` serials."""

    class _Result:
        stdout = (
            "List of devices attached\n"
            "emulator-5554\tdevice\n"
            "emulator-5556\toffline\n"
            "ABCD1234\tdevice\n"  # a physical device, not an emulator
        )

    def fake_run(*args: Any, **kwargs: Any) -> _Result:
        return _Result()

    monkeypatch.setattr(pool_mod.subprocess, "run", fake_run)
    assert pool_mod.running_emulators() == ["emulator-5554"]


def test_allocate_skips_offline_ghost_serial(
    monkeypatch: pytest.MonkeyPatch,
    captured_helpers: list[tuple[str, ...]],
    stub_ports: None,
) -> None:
    """An ``offline`` ghost on 5554 is skipped; the boot lands on the next port.

    Reproduces the real-host failure where ``emulator-5554`` is stuck ``offline``
    (a foreign process holds its adb port 5555). ``running_emulators`` omits it
    (not ``device``), but ``_attached_serials`` reports it, so the pool must skip
    5554 and boot 5556 instead of colliding with the ghost.
    """
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 4)

    def ghost_5554(adb: str = "adb") -> set[str]:
        return {"emulator-5554"}

    monkeypatch.setattr(pool_mod, "_attached_serials", ghost_5554)
    logs: list[str] = []
    pool = EmulatorPool(log=logs.append)

    serials = pool.allocate(1)

    assert serials == ["emulator-5556"]
    boots = [c for c in captured_helpers if c[0] == "emu_boot"]
    assert boots[0][1:4] == ("pixel8_api34", "emulator-5556", "5556")
    assert any("skipping emulator-5554" in line for line in logs)


def test_allocate_skips_port_held_by_foreign_process(
    monkeypatch: pytest.MonkeyPatch,
    captured_helpers: list[tuple[str, ...]],
    stub_ports: None,
) -> None:
    """A console/adb port held by a foreign process (e.g. Celery 5555) is skipped.

    With nothing attached but port 5555 (emulator-5554's adb port) bound, the
    pool must not boot onto 5554 — it skips to 5556.
    """
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 4)

    def busy_5554(port: int) -> bool:
        return port == 5554

    # 5554's adb port (5555) is occupied -> _port_in_use(5554) is True.
    monkeypatch.setattr(pool_mod, "_port_in_use", busy_5554)
    logs: list[str] = []
    pool = EmulatorPool(log=logs.append)

    serials = pool.allocate(1)

    assert serials == ["emulator-5556"]
    assert any("skipping emulator-5554" in line for line in logs)


def test_allocate_terminates_when_every_port_is_poisoned(
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
) -> None:
    """With every probed port occupied, allocate stops (no infinite skip loop).

    Guards the skip path: if no candidate port is ever free, the loop must hit
    its probe ceiling and return without booting, not spin forever.
    """
    _stub_running(monkeypatch, [])
    _stub_cap(monkeypatch, 4)

    def all_busy(port: int) -> bool:
        return True

    def none_attached(adb: str = "adb") -> set[str]:
        return set()

    monkeypatch.setattr(pool_mod, "_attached_serials", none_attached)
    monkeypatch.setattr(pool_mod, "_port_in_use", all_busy)
    logs: list[str] = []
    pool = EmulatorPool(log=logs.append)

    serials = pool.allocate(2)

    assert serials == []  # nothing could boot
    assert [c for c in captured_helpers if c[0] == "emu_boot"] == []
    assert any("no free emulator port" in line for line in logs)


def test_port_in_use_detects_a_bound_port() -> None:
    """``_port_in_use`` reports True for a port a live listener holds, else False."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    bound_port = listener.getsockname()[1]
    try:
        # The helper tests `port` and `port + 1`; bound_port itself is held.
        assert _REAL_PORT_IN_USE(bound_port) is True
    finally:
        listener.close()
    # After close, the port is free again (both port and port+1 unbound).
    assert _REAL_PORT_IN_USE(bound_port) is False


def test_max_parallel_is_at_least_one() -> None:
    """The hardware cap is always >= 1, whatever the host reports."""
    assert pool_mod.max_parallel_emulators() >= 1
