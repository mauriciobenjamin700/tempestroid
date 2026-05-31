"""Python side of the Jetpack Compose device renderer.

The actual rendering happens in Kotlin (`android-host/`). This package provides
the pure-Python half: the ``Style → Compose`` translator that emits a
serializable spec the Kotlin renderer applies. Patch/IR serialization lives in
``tempestroid.bridge``.
"""

from tempestroid.renderers.compose.style_translator import to_compose

__all__ = ["to_compose"]
