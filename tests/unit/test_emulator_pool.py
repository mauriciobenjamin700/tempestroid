"""Unit tests for the F9 emulator pool (allocation logic, adb/subprocess mocked).

No emulator is started: ``adb devices`` and the ``device_loop.sh`` helper calls
are stubbed, so the tests pin the port scheme, the hardware cap, the reuse of
already-running instances, and that a teardown only stops pool-booted serials.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestroid.testing import EmulatorPool
from tempestroid.testing import pool as pool_mod


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
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
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
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
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
    monkeypatch: pytest.MonkeyPatch, captured_helpers: list[tuple[str, ...]]
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


def test_max_parallel_is_at_least_one() -> None:
    """The hardware cap is always >= 1, whatever the host reports."""
    assert pool_mod.max_parallel_emulators() >= 1
