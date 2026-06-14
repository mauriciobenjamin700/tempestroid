"""Allocate and recycle a pool of isolated Android emulators for parallel tests.

:class:`EmulatorPool` hands the F9 runner N **isolated** emulator serials so the
discovered tests shard across real devices and run in parallel. Each instance has
its own console port + serial (port ``5554 + i*2``, serial ``emulator-<port>`` —
the scheme :mod:`toolchain/emulator_pool.sh` uses), is booted ``-read-only`` from
the golden snapshot via the shared :mod:`toolchain/device_loop.sh` helpers
(``emu_boot``/``emu_wait_ready``/``emu_recover``), and is torn down on exit.

Honest about hardware: it caps N by ``nproc`` and available RAM and **logs the
cap** rather than silently shrinking. If an instance is already running (e.g. a
session's ``emulator-5554``), it is **reused** instead of double-booted.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path

__all__ = ["EmulatorPool", "running_emulators", "max_parallel_emulators"]

#: Default AVD booted for a fresh pool instance.
_DEFAULT_AVD = "pixel8_api34"

#: Default snapshot restored on boot (fast, known-clean state).
_DEFAULT_SNAPSHOT = "golden"

#: Base console port; instance ``i`` uses ``_BASE_PORT + i*2`` (adb requires the
#: even console port, odd port+1 is the adb port).
_BASE_PORT = 5554

#: Megabytes of RAM each emulator instance is assumed to need, for the cap.
_RAM_PER_INSTANCE_MB = 2048

#: Absolute hard cap regardless of hardware, so a pathological request cannot
#: fork-bomb the host with emulators.
_HARD_CAP = 8


def running_emulators(adb: str = "adb") -> list[str]:
    """List serials of emulators currently in the ``device`` state.

    Args:
        adb: The ``adb`` executable.

    Returns:
        The ready ``emulator-*`` serials, or ``[]`` when none / adb is missing.
    """
    try:
        out = subprocess.run(  # noqa: S603
            [adb, "devices"], check=False, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return []
    serials: list[str] = []
    for line in out.stdout.splitlines()[1:]:
        parts = line.split()
        if (
            len(parts) == 2
            and parts[1] == "device"
            and parts[0].startswith("emulator-")
        ):
            serials.append(parts[0])
    return serials


def _available_ram_mb() -> int:
    """Estimate free system RAM in MB (Linux ``/proc/meminfo``).

    Returns:
        The available RAM in MB, or a conservative default when unknown.
    """
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return _RAM_PER_INSTANCE_MB  # unknown — allow one instance.
    text = meminfo.read_text(encoding="utf-8")
    match = re.search(r"MemAvailable:\s+(\d+)\s+kB", text)
    if match is None:
        return _RAM_PER_INSTANCE_MB
    return int(match.group(1)) // 1024


def max_parallel_emulators() -> int:
    """Compute the hardware-bounded ceiling on parallel emulator instances.

    Bounds by half the CPU count, available RAM (one instance per
    :data:`_RAM_PER_INSTANCE_MB`), and an absolute :data:`_HARD_CAP`.

    Returns:
        The maximum number of instances the host can reasonably run (>= 1).
    """
    cpus = os.cpu_count() or 2
    by_cpu = max(1, cpus // 2)
    by_ram = max(1, _available_ram_mb() // _RAM_PER_INSTANCE_MB)
    return max(1, min(by_cpu, by_ram, _HARD_CAP))


class EmulatorPool:
    """Allocate, recycle, and tear down a pool of isolated emulator instances.

    Methods:
        allocate: Acquire up to ``n`` ready serials (reusing running ones first).
        release: Mark a serial free (stops a pool-booted instance).
        recycle: Cold-boot a wedged instance via ``emu_recover``.
        teardown: Stop every pool-booted instance.
    """

    def __init__(
        self,
        *,
        avd: str = _DEFAULT_AVD,
        snapshot: str = _DEFAULT_SNAPSHOT,
        adb: str = "adb",
        toolchain_dir: Path | None = None,
        log: Callable[[str], None] = print,
        boot: bool = True,
    ) -> None:
        """Initialize the pool.

        Args:
            avd: The AVD name to boot fresh instances from.
            snapshot: The snapshot to restore on boot.
            adb: The ``adb`` executable.
            toolchain_dir: The repo ``toolchain/`` dir (for ``device_loop.sh``);
                auto-located relative to this file when ``None``.
            log: Sink for status lines (never silent about caps/reuse).
            boot: Boot fresh instances when not enough are running. Set ``False``
                to only ever reuse already-running emulators (no SDK needed).
        """
        self._avd = avd
        self._snapshot = snapshot
        self._adb = adb
        self._log = log
        self._boot = boot
        self._toolchain = toolchain_dir or (
            Path(__file__).resolve().parents[2] / "toolchain"
        )
        # Serials this pool booted itself (and is therefore responsible to stop).
        self._booted: list[str] = []
        # Every serial currently handed out.
        self._allocated: list[str] = []

    def allocate(self, n: int) -> list[str]:
        """Acquire up to ``n`` ready emulator serials.

        Reuses already-running emulators first (no double-boot), then boots fresh
        instances to make up the difference — capped by
        :func:`max_parallel_emulators`. Logs whenever it reuses an instance or
        caps below the request (never a silent shrink).

        Args:
            n: The desired number of instances (clamped to >= 1).

        Returns:
            The list of allocated serials (length <= the hardware cap).
        """
        want = max(1, n)
        ceiling = max_parallel_emulators()
        if want > ceiling:
            self._log(
                f"[pool] capping {want} -> {ceiling} instances "
                f"(hardware: {os.cpu_count()} CPUs, "
                f"{_available_ram_mb()} MB free RAM)"
            )
            want = ceiling

        running = running_emulators(self._adb)
        reused = running[:want]
        if reused:
            joined = ", ".join(reused)
            self._log(f"[pool] reusing running emulator(s): {joined}")
        serials = list(reused)

        if len(serials) < want and not self._boot:
            self._log(
                f"[pool] only {len(serials)} running emulator(s); boot disabled, "
                f"not starting more (wanted {want})"
            )
        index = 0
        while len(serials) < want and self._boot:
            serial = f"emulator-{_BASE_PORT + index * 2}"
            index += 1
            if serial in serials or serial in running:
                continue
            self._boot_instance(serial, _BASE_PORT + (index - 1) * 2)
            serials.append(serial)
            self._booted.append(serial)

        self._allocated = serials
        return serials

    def release(self, serial: str) -> None:
        """Release a serial; stops it only if this pool booted it.

        Args:
            serial: The serial to release.
        """
        if serial in self._allocated:
            self._allocated.remove(serial)
        if serial in self._booted:
            self._run_helper("emu_stop", serial)
            self._booted.remove(serial)

    def recycle(self, serial: str) -> None:
        """Cold-boot a wedged instance via ``emu_recover``.

        Args:
            serial: The serial to recover.
        """
        self._log(f"[pool] recycling wedged emulator {serial}")
        port = _port_for(serial)
        self._run_helper("emu_recover", self._avd, serial, str(port))

    def teardown(self) -> None:
        """Stop every instance this pool booted (reused ones are left running)."""
        for serial in list(self._booted):
            self._run_helper("emu_stop", serial)
        self._booted.clear()
        self._allocated.clear()

    def _boot_instance(self, serial: str, port: int) -> None:
        """Boot and wait for one fresh instance via the toolchain helpers.

        Args:
            serial: The serial to assign.
            port: The console port.
        """
        self._log(f"[pool] booting {serial} (AVD {self._avd}, port {port})")
        self._run_helper("emu_boot", self._avd, serial, str(port), self._snapshot)
        self._run_helper("emu_wait_ready", serial, "180")

    def _run_helper(self, func: str, *args: str) -> None:
        """Invoke a ``device_loop.sh`` helper function in a subshell.

        Sources ``toolchain/device_loop.sh`` then calls ``func`` with ``args``,
        so the pool reuses the exact boot/ready/recover logic the F8 layer ships
        rather than reimplementing it. Failures are surfaced via the log.

        Args:
            func: The shell function name (e.g. ``"emu_boot"``).
            *args: Positional arguments to the function.
        """
        script = self._toolchain / "device_loop.sh"
        quoted = " ".join(shlex.quote(arg) for arg in args)
        command = f". {shlex.quote(str(script))}; {func} {quoted}"
        env = dict(os.environ)
        env.setdefault("ANDROID_SDK_ROOT", "/usr/lib/android-sdk")
        try:
            subprocess.run(  # noqa: S602
                ["bash", "-c", command], check=True, env=env
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._log(f"[pool] helper {func} failed: {exc}")


def _port_for(serial: str) -> int:
    """Extract the console port from an ``emulator-<port>`` serial.

    Args:
        serial: The emulator serial.

    Returns:
        The console port, or :data:`_BASE_PORT` when unparseable.
    """
    match = re.match(r"emulator-(\d+)", serial)
    return int(match.group(1)) if match else _BASE_PORT
