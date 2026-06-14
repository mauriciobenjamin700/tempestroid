"""Quiet, robust Qt platform-plugin defaults for the desktop launchers.

Under WSLg, Qt probes the ``wayland`` platform plugin first; it fails noisily
(``Failed to create wl_display`` / ``Could not load the Qt platform plugin
"wayland"``) and only then falls back to ``xcb``. That same wayland backend is
also the cause of the known WSL "white screen" bug, so defaulting to ``xcb`` on
Linux both silences the startup noise *and* avoids the blank window.

This module sets ``QT_QPA_PLATFORM=xcb`` **before** the ``QApplication`` is
created — but only when the user has not pinned the platform themselves and only
on Linux. It deliberately never overrides:

* an explicit ``QT_QPA_PLATFORM`` (e.g. ``offscreen`` in headless tests/CI, or a
  user who really wants wayland), and
* an explicit ``QT_LOGGING_RULES`` (the user's logging preference wins).

The functions are pure environment mutations, so they can be unit-tested off a
display by inspecting :data:`os.environ`.
"""

from __future__ import annotations

import os
import sys

__all__ = ["configure_qt_platform", "prefer_xcb_on_linux", "quiet_qpa_probe"]

#: The platform plugin we default to on Linux. ``xcb`` is the X11 backend, which
#: works reliably under WSLg's X server and does not emit the wayland probe noise.
_DEFAULT_LINUX_PLATFORM = "xcb"

#: Logging rules that mute only the Qt platform-abstraction (``qpa``) category, so
#: any residual probe chatter is hidden without silencing the rest of Qt.
_QUIET_QPA_RULE = "qt.qpa.*=false"


def prefer_xcb_on_linux() -> None:
    """Default ``QT_QPA_PLATFORM`` to ``xcb`` on Linux when the user left it unset.

    Call this **before** constructing the ``QApplication``. On non-Linux
    platforms it is a no-op. On Linux it sets ``QT_QPA_PLATFORM=xcb`` only when
    the variable is absent (or empty), so an explicit user choice —
    ``offscreen`` for headless tests, ``wayland`` for a native wayland session,
    or any other value — is always respected.

    Why ``xcb``: under WSLg, Qt's default plugin search hits ``wayland`` first,
    which fails noisily and then falls back to ``xcb``; pinning ``xcb`` up front
    skips the failed wayland probe (silencing the warnings) and sidesteps the
    known WSL wayland "white screen" bug.
    """
    if not sys.platform.startswith("linux"):
        return
    # `setdefault`-style guard: only set when the user has not pinned a platform.
    # An empty string counts as unset (a stray `QT_QPA_PLATFORM=` should not pin
    # an invalid empty plugin name).
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    os.environ["QT_QPA_PLATFORM"] = _DEFAULT_LINUX_PLATFORM


def quiet_qpa_probe() -> None:
    """Mute the Qt platform-abstraction logging category when the user left it unset.

    A defensive companion to :func:`prefer_xcb_on_linux`: even after pinning
    ``xcb``, set ``QT_LOGGING_RULES=qt.qpa.*=false`` so any remaining platform
    probe chatter (e.g. on a host that still tries wayland) stays quiet. Only
    applied when ``QT_LOGGING_RULES`` is unset — an explicit user rule wins and
    is never clobbered or appended to.
    """
    if os.environ.get("QT_LOGGING_RULES"):
        return
    os.environ["QT_LOGGING_RULES"] = _QUIET_QPA_RULE


def configure_qt_platform() -> None:
    """Apply both quiet-launch defaults in the right order.

    Convenience entry point for the desktop launchers: prefer ``xcb`` on Linux
    and mute the ``qpa`` logging category, each only when the user has not set
    the corresponding environment variable. Must run before the ``QApplication``
    is created.
    """
    prefer_xcb_on_linux()
    quiet_qpa_probe()
