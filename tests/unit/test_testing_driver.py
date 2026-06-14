"""Unit tests for the F9 native UI test driver (headless backend).

These exercise the driver end to end with no renderer: an in-process counter app
is driven through the same ``event → handler → state → rebuild → diff → patch``
loop a device would, and the auto-wait/locator/assertion surface is verified.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from tempest_core.widgets.events import TapEvent, TextChangeEvent

from tempestroid import App, Button, Column, Semantics, Text, Widget
from tempestroid.testing import (
    HeadlessBackend,
    Locator,
    LocatorError,
    Page,
    run_test_file,
)
from tempestroid.testing import TestBackend as _TestBackend
from tempestroid.testing.backend import event_schema_for


@dataclass
class CounterState:
    """Mutable counter state.

    Attributes:
        value: The current count.
    """

    value: int = 0


def make_state() -> CounterState:
    """Build a fresh counter state.

    Returns:
        A new state at zero.
    """
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Build the counter UI.

    Args:
        app: The running app.

    Returns:
        The counter screen.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    async def increment_later() -> None:
        await asyncio.sleep(0)
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        children=[
            Text(
                content=f"Count: {app.state.value}",
                key="label",
                semantics=Semantics(label="counter", role="heading"),
            ),
            Button(label="+", on_click=increment, key="inc"),
            Button(label="+ async", on_click=increment_later, key="async"),
        ],
    )


def _page() -> Page:
    """Build a page over a fresh headless counter backend.

    Returns:
        An unmounted :class:`Page`.
    """
    return Page(HeadlessBackend(make_state, view))


async def test_headless_backend_is_a_test_backend() -> None:
    """The headless backend satisfies the :class:`TestBackend` protocol."""
    assert isinstance(HeadlessBackend(make_state, view), _TestBackend)


async def test_initial_text_is_visible() -> None:
    """The mounted counter shows ``Count: 0``."""
    page = _page()
    await page.mount()
    await page.expect_text("Count: 0")


async def test_get_by_key_resolves_against_live_scene() -> None:
    """A key locator finds the labelled node after mount."""
    page = _page()
    await page.mount()
    label = page.get_by_key("label")
    assert label.first.type == "Text"
    assert label.count() == 1


async def test_tap_increments_with_auto_wait() -> None:
    """Tapping ``+`` increments the count and auto-wait sees the new value."""
    page = _page()
    await page.mount()
    await page.tap(page.get_by_key("inc"))
    await page.expect_text("Count: 1")
    await page.tap(page.get_by_key("inc"))
    await page.expect_text("Count: 2")


async def test_async_handler_settles_before_assert() -> None:
    """An async handler's state update is awaited before the assertion proceeds."""
    page = _page()
    await page.mount()
    await page.tap(page.get_by_key("async"))
    await page.expect_text("Count: 1")


async def test_get_by_role_and_semantics() -> None:
    """Role and semantics locators read the node's accessibility metadata."""
    page = _page()
    await page.mount()
    assert page.get_by_role("heading").count() == 1
    assert page.get_by_role("heading", name="counter").count() == 1
    assert page.get_by_role("heading", name="nope").count() == 0
    assert page.get_by_semantics(label="counter").count() == 1


async def test_get_by_text_substring_and_exact() -> None:
    """Text locator matches by substring by default and whole-text when exact."""
    page = _page()
    await page.mount()
    assert page.get_by_text("Count").count() >= 1
    assert page.get_by_text("Count: 0", exact=True).count() == 1
    assert page.get_by_text("Count", exact=True).count() == 0


async def test_patches_recorded_after_action() -> None:
    """A tap produces a recorded patch batch (the diff the renderer would apply)."""
    page = _page()
    await page.mount()
    assert page.backend.patches() == []
    await page.tap(page.get_by_key("inc"))
    assert len(page.backend.patches()) >= 1


async def test_expect_text_times_out_when_never_true() -> None:
    """An assertion that can never hold raises after the timeout, not hangs."""
    page = _page()
    await page.mount()
    with pytest.raises(AssertionError, match="to be visible"):
        await page.expect_text("Count: 999", timeout=0.2)


async def test_locator_not_found_raises() -> None:
    """Resolving a locator that matches nothing raises a clear error."""
    page = _page()
    await page.mount()
    with pytest.raises(LocatorError, match="no node matches"):
        page.get_by_key("missing").resolve()


async def test_locator_ambiguous_raises() -> None:
    """Resolving a locator that matches many nodes raises rather than guessing."""
    page = _page()
    await page.mount()
    # Both buttons carry "+" in their visible text (and the container aggregates
    # its children's text), so the substring locator matches more than one node.
    ambiguous = page.get_by_text("+")
    assert ambiguous.count() >= 2
    with pytest.raises(LocatorError, match="matched .* nodes"):
        ambiguous.resolve()


async def test_tap_on_ambiguous_locator_raises() -> None:
    """An action on an ambiguous locator fails loudly."""
    page = _page()
    await page.mount()
    with pytest.raises(LocatorError):
        await page.tap(page.get_by_text("+"))


async def test_snapshot_is_json_able_and_reflects_state() -> None:
    """``snapshot`` dumps a stable, JSON-able tree that tracks state."""
    import json

    page = _page()
    await page.mount()
    before = page.snapshot()
    assert json.dumps(before)  # serializable
    assert before["root"]["type"] == "Column"
    await page.tap(page.get_by_key("inc"))
    await page.expect_text("Count: 1")
    after = page.snapshot()
    assert after != before


async def test_back_without_nav_support_is_noop_pop() -> None:
    """``back`` pops the app's nav stack; at root it is a safe no-op."""
    page = _page()
    await page.mount()
    # Single-screen app: pop at root is a no-op and must not raise.
    await page.back()
    await page.expect_text("Count: 0")


async def test_get_by_returns_locator() -> None:
    """``get_by_*`` constructors return :class:`Locator` instances."""
    page = _page()
    await page.mount()
    loc: Locator = page.get_by_key("x")
    assert isinstance(loc, Locator)
    assert isinstance(page.get_by_text("Count"), Locator)
    assert isinstance(page.get_by_role("heading"), Locator)


def test_event_schema_resolution() -> None:
    """The schema index maps widget handlers to their typed events with fallbacks."""
    assert event_schema_for("Button", "on_click") is TapEvent
    assert event_schema_for("Input", "on_change") is TextChangeEvent
    # Unknown widget, value-bearing handler name → TextChangeEvent fallback.
    assert event_schema_for("Mystery", "on_change") is TextChangeEvent
    # Unknown widget + handler → TapEvent fallback.
    assert event_schema_for("Mystery", "on_poke") is TapEvent


def test_run_test_file_on_example_passes() -> None:
    """The example UI test file runs green via the headless runner."""
    example = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "counter"
        / "test_counter.py"
    )
    report = run_test_file(example, target="headless")
    assert report.outcomes, "expected discovered tests"
    assert report.passed, [(o.name, o.message) for o in report.failures]


def test_run_test_file_rejects_planned_target() -> None:
    """Selecting an F8 target raises NotImplementedError pointing at F8."""
    example = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "counter"
        / "test_counter.py"
    )
    with pytest.raises(NotImplementedError, match="F8"):
        run_test_file(example, target="emulator")


def test_run_test_file_reports_failures_with_tree_dump(tmp_path: Path) -> None:
    """A failing test is captured as a failure with a tree dump, others still run."""
    src = """
from dataclasses import dataclass

from tempestroid import App, Text, Widget


@dataclass
class S:
    n: int = 0


def make_state() -> S:
    return S()


def view(app: App[S]) -> Widget:
    return Text(content="hello", key="t")


async def test_passes(page) -> None:
    await page.expect_text("hello")


async def test_fails(page) -> None:
    await page.expect_text("never here", timeout=0.1)
"""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(src, encoding="utf-8")
    report = run_test_file(test_file, target="headless")
    names = {o.name: o for o in report.outcomes}
    assert names["test_passes"].passed
    assert not names["test_fails"].passed
    assert not report.passed
    assert names["test_fails"].tree_dump  # the failing scene was captured
