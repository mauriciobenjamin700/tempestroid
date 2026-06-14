"""Tests for the Qt desktop launcher's platform-plugin defaults.

These exercise :mod:`tempestroid.renderers.qt.platform_setup` as pure
environment mutations — no ``QApplication`` and no display required — so they
run unchanged under ``QT_QPA_PLATFORM=offscreen`` in CI. The critical invariant
is that the helpers only set a variable when the user left it unset, so the
``offscreen`` headless default in :mod:`tests.conftest` is never clobbered.
"""

from __future__ import annotations

import pytest

from tempestroid.renderers.qt.platform_setup import (
    configure_qt_platform,
    prefer_xcb_on_linux,
    quiet_qpa_probe,
)


def test_prefer_xcb_sets_default_on_linux_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Linux with no pinned platform, ``QT_QPA_PLATFORM`` defaults to ``xcb``."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    prefer_xcb_on_linux()

    import os

    assert os.environ["QT_QPA_PLATFORM"] == "xcb"


def test_prefer_xcb_respects_explicit_offscreen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit ``offscreen`` (headless tests/CI) is never overridden."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    prefer_xcb_on_linux()

    import os

    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_prefer_xcb_respects_explicit_wayland(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user who pinned ``wayland`` keeps it — the default does not win."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("QT_QPA_PLATFORM", "wayland")

    prefer_xcb_on_linux()

    import os

    assert os.environ["QT_QPA_PLATFORM"] == "wayland"


def test_prefer_xcb_treats_empty_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty ``QT_QPA_PLATFORM=`` is treated as unset and gets the default."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("QT_QPA_PLATFORM", "")

    prefer_xcb_on_linux()

    import os

    assert os.environ["QT_QPA_PLATFORM"] == "xcb"


def test_prefer_xcb_is_noop_off_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """On non-Linux platforms the helper does not touch ``QT_QPA_PLATFORM``."""
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    prefer_xcb_on_linux()

    import os

    assert "QT_QPA_PLATFORM" not in os.environ


def test_quiet_qpa_probe_sets_rule_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When unset, the qpa logging category is muted."""
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)

    quiet_qpa_probe()

    import os

    assert os.environ["QT_LOGGING_RULES"] == "qt.qpa.*=false"


def test_quiet_qpa_probe_respects_existing_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit user logging rule is never clobbered or appended to."""
    monkeypatch.setenv("QT_LOGGING_RULES", "qt.svg.warning=true")

    quiet_qpa_probe()

    import os

    assert os.environ["QT_LOGGING_RULES"] == "qt.svg.warning=true"


def test_configure_applies_both_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """The convenience entry point applies both defaults when both are unset."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)

    configure_qt_platform()

    import os

    assert os.environ["QT_QPA_PLATFORM"] == "xcb"
    assert os.environ["QT_LOGGING_RULES"] == "qt.qpa.*=false"
