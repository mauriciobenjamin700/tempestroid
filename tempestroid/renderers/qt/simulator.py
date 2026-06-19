"""A hot-restartable Qt simulator window for the dev loop.

Wraps a :class:`QtRenderer` and the current :class:`App`. ``load`` (re)builds the
app from an :class:`AppSpec` and remounts it with clean state — this is the hot
*restart* the dev cockpit triggers on save or on the ``R`` command. (Stateful hot
*reload* is post-v1; v1 is restart-only, the order Flutter itself followed.)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget
from tempest_core.core.ir import Patch
from tempest_core.core.state import App

from tempestroid.cli.app_loader import AppSpec
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

        This is the hot *restart*: state is discarded (``make_state`` runs) and
        the tree is fully remounted.

        Args:
            spec: The app spec to instantiate.
        """
        app: App[Any] = App(
            spec.make_state(),
            spec.view,
            apply_patches=self._apply_with_context,
            theme=spec.make_theme() if spec.make_theme is not None else None,
        )
        # `App.start` builds a `Scene`; the Qt renderer mounts its root tree and
        # floating overlay layer, routing host-owned dismissals to `App.dismiss`.
        self.renderer.set_dismiss_overlay(app.dismiss)
        # Wire the live app so the renderer reads theme/locale/media context (E9).
        self.renderer.set_app(app)
        self.renderer.remount(app.start())
        self._app = app

    def _apply_with_context(self, patches: list[Patch]) -> None:
        """Apply a coalesced patch batch then re-sync the theme/locale context.

        Mirrors ``run_qt``: after each batch the renderer re-reads the app's
        ``theme``/``locale`` so a ``set_theme``/``set_locale`` (which only
        schedules a rebuild) takes visual effect (palette swap + layout
        direction).

        Args:
            patches: The patch batch from the reconciler.
        """
        self.renderer.apply(patches)
        self.renderer.sync_context()

    def reload(self, spec: AppSpec) -> None:
        """Hot-*reload* the app from a spec, preserving the live state.

        Swaps the running app's view for the reloaded one and reconciles via a
        diff, so the on-screen state survives the edit. If no app is loaded yet,
        or the new view is incompatible with the preserved state, this falls back
        to a clean :meth:`load` (restart) so the dev loop never wedges.

        Args:
            spec: The reloaded app spec.
        """
        if self._app is None:
            self.load(spec)
            return
        try:
            self._app.swap_view(spec.view)
        except Exception:  # noqa: BLE001 — incompatible reload → clean restart
            self.load(spec)
