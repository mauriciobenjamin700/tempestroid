"""A hot-restartable Qt simulator window for the dev loop.

Wraps a :class:`QtRenderer` and the current :class:`App`. ``load`` (re)builds the
app from an :class:`AppSpec` and remounts it with clean state — this is the hot
*restart* the dev cockpit triggers on save or on the ``R`` command. (Stateful hot
*reload* is post-v1; v1 is restart-only, the order Flutter itself followed.)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from tempestroid.cli.app_loader import AppSpec
from tempestroid.core.state import App
from tempestroid.renderers.qt.renderer import QtRenderer

__all__ = ["Simulator"]


class Simulator:
    """Owns the simulator window and hot-restarts the running app."""

    def __init__(self) -> None:
        """Create the simulator with an empty renderer."""
        self.renderer: QtRenderer = QtRenderer()
        self._app: App[Any] | None = None

    @property
    def host(self) -> QWidget:
        """The host widget to show in a window.

        Returns:
            The renderer's host widget.
        """
        return self.renderer.host

    @property
    def app(self) -> App[Any]:
        """The currently loaded app.

        Returns:
            The active app.

        Raises:
            RuntimeError: If no app has been loaded yet.
        """
        if self._app is None:
            raise RuntimeError("no app loaded")
        return self._app

    def load(self, spec: AppSpec) -> None:
        """(Re)build the app from a spec and remount it with clean state.

        Args:
            spec: The app spec to instantiate.
        """
        app: App[Any] = App(
            spec.make_state(), spec.view, apply_patches=self.renderer.apply
        )
        self.renderer.remount(app.start())
        self._app = app
