"""UI test for the numpy spike — proves ``import numpy`` works on the device.

Run headless (numpy is also importable on the desktop) with::

    uv run tempest uitest examples/onnxspike/test_onnxspike.py

and on the emulator (the real proof — the cross-compiled ``android_24_x86_64``
numpy wheel) with::

    uv run tempest uitest examples/onnxspike/test_onnxspike.py --target emulator

The app renders "numpy OK" (green) plus the version + a computed result when numpy
imports and computes, or "numpy FAILED" (red) with the traceback otherwise — so a
passing test means numpy genuinely ran inside the embedded interpreter.
"""

from __future__ import annotations

from app import make_state, view  # noqa: F401 — the app contract the driver loads

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_numpy_imports_and_computes(page: Page) -> None:
    """numpy imports and a small array computation runs on the target."""
    await page.expect_text("numpy OK")
    # The detail line carries the version + computed sum (1..10 -> 55).
    await page.expect_text("sum=55")
