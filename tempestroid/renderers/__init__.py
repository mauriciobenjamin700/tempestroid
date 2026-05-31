"""Leaf renderers.

Each renderer applies reconciler patches in its own technology — Qt on the
desktop simulator, Jetpack Compose on the device. The ``qt`` subpackage requires
the optional ``qt`` extra, so it is imported on demand rather than re-exported
here.
"""

__all__: list[str] = []
