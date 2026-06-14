"""UI tests for the counter example, driven by the F9 native test driver.

Run them in the headless backend (no Qt, no device) with::

    uv run tempest uitest examples/counter/test_counter.py

A UI test file is an ordinary app module — it must expose ``view`` and
``make_state`` (here re-used from the sibling ``app.py``) — plus one or more
``async def test_*(page)`` functions. Each test gets a fresh :class:`Page` over a
fresh in-process app; every action and assertion auto-waits for the tree to
settle, so there are no ``sleep`` calls and no flake.

Because the driver speaks the renderer-agnostic IR + typed events, this exact
script will run on the Qt simulator and the emulator/device once those backends
land (Trilho F8) — no change to the test.
"""

from __future__ import annotations

from app import make_state, view  # noqa: F401 — the app contract the driver loads

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_counter_starts_at_zero(page: Page) -> None:
    """The counter shows ``Count: 0`` on first mount."""
    await page.expect_text("Count: 0")


async def test_increment_button_updates_count(page: Page) -> None:
    """Tapping ``+`` increments the count, and auto-wait sees the new value."""
    await page.expect_text("Count: 0")
    await page.tap(page.get_by_key("inc"))
    await page.expect_text("Count: 1")


async def test_async_handler_settles_before_assert(page: Page) -> None:
    """An async handler (`+ (async)`) eventually updates; auto-wait waits it out."""
    await page.tap(page.get_by_key("async"))
    await page.expect_text("Count: 1")
