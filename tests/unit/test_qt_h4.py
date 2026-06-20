"""Qt renderer tests for the H4 data-display & feedback kit.

Most H4 components (Alert/Badge/Chip/Tag/Stat/ProgressStepper/Banner) are
``Component``s that lower to primitives carrying a theme-resolved ``Style``, so
the Qt renderer handles them through the generic path — no new node type. The
leaf widgets that DO reach the renderer (``ProgressBar``/``Spinner``) gain a
``color_scheme`` accent (H4): the renderer must tint the ``::chunk`` with the
resolved Material 3 accent. These tests pin that accent + that the lowered
feedback components mount.
"""

from __future__ import annotations

from PySide6.QtWidgets import QProgressBar
from tempest_core.components import Alert, Badge, Stat
from tempest_core.core.reconciler import build
from tempest_core.style import AlertVariant, BadgeVariant
from tempest_core.theme import Theme
from tempest_core.tokens import ColorRole
from tempest_core.widgets import ProgressBar

from tempestroid.renderers.qt.renderer import QtRenderer


def test_progressbar_chunk_uses_color_scheme_accent(qapp: object) -> None:
    """A ``ProgressBar`` tints its ``::chunk`` with the color_scheme accent.

    Regression guard: H4 added ``color_scheme`` to ``ProgressBar``; the Qt
    renderer must paint the resolved Material 3 role accent on the filled chunk
    (so a ``success`` bar reads green), not leave the Qt default blue.
    """
    renderer = QtRenderer()
    renderer.mount(build(ProgressBar(value=0.5, color_scheme="success")))
    bar = renderer.host.findChild(QProgressBar)
    assert isinstance(bar, QProgressBar)
    qss = bar.styleSheet()
    assert "::chunk" in qss
    accent = Theme().scheme().role(ColorRole.SUCCESS)
    assert accent.to_rgba_string() in qss


def test_progressbar_defaults_to_primary_accent(qapp: object) -> None:
    """A ``ProgressBar`` defaults its accent to the ``primary`` role.

    ``color_scheme`` defaults to ``"primary"`` (M3-consistent), so a plain
    ``ProgressBar`` always tints its chunk with the primary accent — never the
    raw Qt default blue.
    """
    renderer = QtRenderer()
    renderer.mount(build(ProgressBar(value=0.5)))
    bar = renderer.host.findChild(QProgressBar)
    assert isinstance(bar, QProgressBar)
    qss = bar.styleSheet()
    assert "::chunk" in qss
    accent = Theme().scheme().role(ColorRole.PRIMARY)
    assert accent.to_rgba_string() in qss


def test_alert_lowers_and_mounts(qapp: object) -> None:
    """A styled ``Alert`` lowers to a primitive tree and mounts without error."""
    node = build(
        Alert(title="Heads up", body="A subtle info alert.", color_scheme="info",
              variant=AlertVariant.SUBTLE)
    )
    renderer = QtRenderer()
    renderer.mount(node)


def test_badge_and_stat_lower_and_mount(qapp: object) -> None:
    """A ``Badge`` and a ``Stat`` lower to primitives and mount."""
    renderer = QtRenderer()
    renderer.mount(build(Badge(label="new", color_scheme="success",
                               variant=BadgeVariant.SOLID)))
    renderer.mount(build(Stat(label="Revenue", value="12k", delta="+8%",
                              delta_up=True)))
