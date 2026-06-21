"""Qt renderer tests for the H3 surface & layout kit.

H3 surfaces (``Card``/``Surface``/``HStack``/``VStack``) are ``Component``s that
lower to primitives (``Container``/``Row``/``Column``) carrying a theme-resolved
``Style``, so the Qt renderer handles them through the generic primitive path —
no new node type. The one new *leaf* is ``Spacer``, which DOES reach the renderer
and must be handled (a flexible gap whose baked ``grow`` drives the parent
stretch). These tests pin that surfaces lower + render and that ``Spacer`` is a
known node type.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from tempest_core.components import Card, Surface
from tempest_core.core.reconciler import build
from tempest_core.style import CardVariant
from tempest_core.widgets import Spacer

from tempestroid.renderers.qt.renderer import QtRenderer


def test_spacer_is_a_known_node_type(qapp: object) -> None:
    """A ``Spacer`` mounts without raising ``unknown node type``.

    Regression guard: ``Spacer`` is a new H3 leaf widget; the Qt renderer must
    map it to a widget (a flexible gap) rather than rejecting it.
    """
    renderer = QtRenderer()
    renderer.mount(build(Spacer()))
    # The spacer mounted as a real QWidget under the host (no "unknown node type").
    assert renderer.host.findChildren(QWidget)


def test_card_lowers_and_renders(qapp: object) -> None:
    """A styled ``Card`` lowers to a primitive and mounts without error.

    The Card resolves its surface ``Style`` from the theme at ``render()`` time
    and folds it into a ``Container``; the renderer never sees the ``Card``
    Component itself.
    """
    node = build(Card(variant=CardVariant.ELEVATED, children=[]))
    assert node.type == "Container"
    renderer = QtRenderer()
    renderer.mount(node)


def test_surface_lowers_to_container(qapp: object) -> None:
    """A ``Surface`` lowers to a primitive ``Container`` and mounts."""
    node = build(Surface(variant=CardVariant.FILLED))
    assert node.type == "Container"
    renderer = QtRenderer()
    renderer.mount(node)
