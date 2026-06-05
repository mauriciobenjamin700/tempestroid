"""Render a device-visible error screen when an app fails to load or boot.

The device entry points (the baked-APK runners in
:mod:`tempestroid.bridge.jni` and the code-push client in
:mod:`tempestroid.devserver.client`) ``exec`` arbitrary user app source. If that
exec — or the first build — raises (a top-level ``import`` of the Qt renderer is
the classic one, since PySide6 is absent on the device), the renderer would
otherwise show a blank white screen with the traceback buried in ``logcat``.

This module turns such a failure into a visible red error screen on the device,
so the developer sees *what* broke without attaching ``adb`` — the on-device
analogue of the desktop dev loop printing a caught exception.
"""

from __future__ import annotations

from tempestroid.style import Color, Edge, FlexDirection, FontWeight, Style
from tempestroid.widgets import Column, Text, Widget

__all__ = ["error_screen"]


def error_screen(title: str, detail: str) -> Widget:
    """Build a full-screen error view (red background, title + detail).

    Args:
        title: A short, human summary (e.g. ``"App failed to load"``).
        detail: The error detail / traceback shown beneath the title.

    Returns:
        The root widget of the error screen.
    """
    return Column(
        style=Style(
            direction=FlexDirection.COLUMN,
            gap=12.0,
            padding=Edge.all(20.0),
            background=Color.from_hex("#3b0d0d"),
        ),
        children=[
            Text(
                content=title,
                style=Style(
                    color=Color.from_hex("#fca5a5"),
                    font_size=20.0,
                    font_weight=FontWeight.BOLD,
                ),
                key="error-title",
            ),
            Text(
                content=detail,
                style=Style(color=Color.from_hex("#fecaca"), font_size=13.0),
                key="error-detail",
            ),
        ],
    )
