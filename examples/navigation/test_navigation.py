"""UI tests for the navigation example, driven by the F9 native test driver.

Run them in the headless backend (no Qt, no device) with::

    uv run tempest uitest examples/navigation/test_navigation.py

A UI test file is an ordinary app module — it re-uses ``view`` and ``make_state``
from the sibling ``app.py`` — plus ``async def test_*(page)`` functions. Each test
gets a fresh :class:`Page` over a fresh in-process app; every action and assertion
auto-waits for the tree to settle (no ``sleep`` calls, no flake).

Because the driver speaks the renderer-agnostic IR + typed events, this exact
script also runs on the emulator/device (``--target emulator``) — the Navigator
push/pop is real ``app.nav`` state, so the same assertions hold on both.
"""

from __future__ import annotations

from app import make_state, view  # noqa: F401 — the app contract the driver loads

from tempestroid.testing import Page

__all__ = ["make_state", "view"]


async def test_starts_on_the_root_route(page: Page) -> None:
    """The Stack tab opens on the root route ``/``."""
    await page.expect_text("route: /")


async def test_push_navigates_to_next_screen(page: Page) -> None:
    """Tapping ``push`` pushes a screen; the route reflects the new top."""
    await page.expect_text("route: /")
    await page.tap(page.get_by_key("push"))
    await page.expect_text("route: /stack/1")


async def test_pop_returns_to_previous_screen(page: Page) -> None:
    """Tapping ``pop`` after a push returns to the root route."""
    await page.tap(page.get_by_key("push"))
    await page.expect_text("route: /stack/1")
    await page.tap(page.get_by_key("pop"))
    await page.expect_text("route: /")


async def test_system_back_pops_the_stack(page: Page) -> None:
    """The system back action (``page.back()``) pops a pushed screen."""
    await page.tap(page.get_by_key("push"))
    await page.expect_text("route: /stack/1")
    await page.back()
    await page.expect_text("route: /")
