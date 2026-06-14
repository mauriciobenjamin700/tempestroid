"""Qt leaf renderer for the desktop simulator.

Importing this package requires the optional ``qt`` extra (PySide6). It exposes
the renderer and the ``Style -> Qt`` translator.
"""

from tempestroid.renderers.qt.app_runner import BackKeyFilter, run_qt
from tempestroid.renderers.qt.dev_loop import run_dev
from tempestroid.renderers.qt.platform_setup import (
    configure_qt_platform,
    prefer_xcb_on_linux,
    quiet_qpa_probe,
)
from tempestroid.renderers.qt.renderer import QtRenderer
from tempestroid.renderers.qt.simulator import Simulator
from tempestroid.renderers.qt.style_translator import layout_alignment, to_qss

__all__ = [
    "QtRenderer",
    "Simulator",
    "run_qt",
    "run_dev",
    "to_qss",
    "layout_alignment",
    "BackKeyFilter",
    "configure_qt_platform",
    "prefer_xcb_on_linux",
    "quiet_qpa_probe",
]
