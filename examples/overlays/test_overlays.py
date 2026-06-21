"""UI tests for the overlays example, driven by the F9 native test driver.

Run them in the headless backend (no Qt, no device) with::

    uv run tempest uitest examples/overlays/test_overlays.py

Each test gets a fresh :class:`Page` over a fresh in-process app and auto-waits
for the tree (root + overlay layer) to settle. The same script runs on the
emulator/device (``--target emulator``) — overlays are real ``App.show_dialog`` /
``show_sheet`` / ``dismiss`` state, so the assertions hold on both renderers.
"""

from __future__ import annotations

from app import make_state, view  # noqa: F401 — the app contract the driver loads

from tempestroid.testing import Page

__all__ = ["make_state", "view"]

_DIALOG_BODY = "This dialog blocks taps behind it (barrier)."
_SHEET_BODY = "A bottom sheet slid up from the edge."


async def test_open_dialog_shows_its_content(page: Page) -> None:
    """Tapping the dialog button opens a dialog with its body text."""
    await page.expect_count(page.get_by_text(_DIALOG_BODY), 0)
    await page.tap(page.get_by_key("dialog-btn"))
    await page.expect_text(_DIALOG_BODY)


async def test_close_dialog_dismisses_it(page: Page) -> None:
    """Tapping the dialog's Close button removes the overlay."""
    await page.tap(page.get_by_key("dialog-btn"))
    await page.expect_text(_DIALOG_BODY)
    await page.tap(page.get_by_key("dlg-close"))
    await page.expect_count(page.get_by_text(_DIALOG_BODY), 0)


async def test_open_bottom_sheet_shows_its_content(page: Page) -> None:
    """Tapping the sheet button slides up a bottom sheet with its body text."""
    await page.tap(page.get_by_key("sheet-btn"))
    await page.expect_text(_SHEET_BODY)
