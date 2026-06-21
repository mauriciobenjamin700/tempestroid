"""Per-agent adb-server isolation for parallel emulator runs.

The emulator *instances* a pool boots are already isolated — each has its own
console/adb port, ``-read-only`` userdata, and serial (see
:mod:`tempestroid.testing.pool`). The one resource that stays **shared** under
parallel load is the adb server itself: by default every ``adb`` and ``emulator``
process on the host talks to a single server on TCP ``5037``. When two agents
drive emulators at once they both hammer that one server, it wedges under the
combined load, and the recovery path used to ``SIGKILL`` *every* ``adb`` process —
taking down the sibling agent's server too.

The fix is one server **per agent**. Both ``adb`` and the ``emulator`` binary
honor the ``ANDROID_ADB_SERVER_PORT`` environment variable: give each agent a
distinct port and each gets a private server that only its own emulators register
with, so agents never contend and a recovery only ever resets the agent's own
server.

This module is the single seam for that: it derives/allocates the private port
and builds the environment mapping that :mod:`tempestroid.testing.pool`, the
:class:`~tempestroid.testing.emulator.EmulatorBackend`, and the
``device_loop.sh`` helpers thread through every adb/emulator subprocess.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping

__all__ = [
    "ADB_SERVER_PORT_ENV",
    "DEFAULT_ADB_SERVER_PORT",
    "current_adb_server_port",
    "allocate_adb_server_port",
    "adb_server_env",
]

#: The environment variable both ``adb`` and ``emulator`` read to choose which
#: adb server to talk to / register with.
ADB_SERVER_PORT_ENV = "ANDROID_ADB_SERVER_PORT"

#: adb's built-in default server port (the shared, non-isolated server).
DEFAULT_ADB_SERVER_PORT = 5037

#: Port band for private (per-agent) adb servers: strictly above adb's shared
#: default (5037) and well below the emulator console/adb port band (5554+), so
#: an isolated server can never collide with the shared server or any emulator's
#: own ports.
_AGENT_PORT_BASE = 5038
_AGENT_PORT_CEILING = 5500


def current_adb_server_port() -> int | None:
    """Return the adb server port from the environment, if isolation is active.

    Returns:
        The ``ANDROID_ADB_SERVER_PORT`` value as an ``int``, or ``None`` when the
        variable is unset or non-numeric (meaning the shared default ``5037``
        server is in use).
    """
    raw = os.environ.get(ADB_SERVER_PORT_ENV)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _port_free(port: int) -> bool:
    """Whether a TCP port on localhost is free (nothing is listening).

    Args:
        port: The port to probe.

    Returns:
        ``True`` if a connect attempt is refused (port free), ``False`` if a
        listener answers.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def allocate_adb_server_port(preferred: int | None = None) -> int:
    """Pick a free TCP port for a private (per-agent) adb server.

    Args:
        preferred: A specific port to use when it is free (e.g. a deterministic
            per-agent choice); when busy or ``None`` the band is scanned.

    Returns:
        A free port in the per-agent band, distinct from the shared ``5037``
        server and the emulator console/adb band.

    Raises:
        RuntimeError: If no free port is available in the band.
    """
    if preferred is not None and _port_free(preferred):
        return preferred
    for port in range(_AGENT_PORT_BASE, _AGENT_PORT_CEILING):
        if _port_free(port):
            return port
    raise RuntimeError(
        f"no free adb-server port in {_AGENT_PORT_BASE}..{_AGENT_PORT_CEILING}"
    )


def adb_server_env(
    port: int | None, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build an environment mapping pinned to an adb server port.

    Args:
        port: The adb server port to pin. When ``None`` the base environment is
            returned unchanged (the caller inherits whatever server is already
            configured — the shared default, or an externally-set
            ``ANDROID_ADB_SERVER_PORT``).
        base: The environment to extend; defaults to a copy of ``os.environ``.

    Returns:
        A new ``dict`` with :data:`ADB_SERVER_PORT_ENV` set to ``port`` (a copy of
        the base environment unchanged when ``port`` is ``None``).
    """
    env = dict(os.environ if base is None else base)
    if port is not None:
        env[ADB_SERVER_PORT_ENV] = str(port)
    return env
