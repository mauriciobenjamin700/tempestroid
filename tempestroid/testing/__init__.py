"""tempestroid.testing — a Playwright-style UI test driver for the native IR.

The driver automates an app the way Playwright automates a web page, but against
the framework's **renderer-agnostic IR** rather than a DOM: it mounts an app,
locates nodes by stable key / visible text / accessibility semantics, injects the
same typed events a real tap or keystroke produces, and asserts the resulting UI
state — with **auto-wait** built into every action and assertion (the tree must
settle before proceeding; no fixed sleeps), so timing flake disappears.

Because every backend speaks the same IR + typed-event vocabulary, one test
script runs against every target. This slice ships the **headless** backend
(:class:`HeadlessBackend`) — it drives the
:class:`~tempestroid.core.state.App`/IR/event core in-process with no renderer,
exercising the full ``event → handler → state → rebuild → diff → patch`` loop
deterministically. The Qt-window and emulator/device backends slot in behind the
same :class:`TestBackend` protocol once Trilho F8 lands the stable targets — the
:class:`Page`/:class:`Locator`/assertion surface is unchanged, so **the same test
will run on Qt and on the emulator/device**.

Public surface:

* :class:`Page` — the top-level driver (locators, actions, auto-waiting asserts).
* :class:`Locator` — a lazy, late-resolving node query.
* :class:`TestBackend` — the protocol a renderer target implements.
* :class:`HeadlessBackend` — the no-renderer reference backend.
* :func:`run_test_file` — load + run a UI test file's ``test_*`` functions.
"""

from __future__ import annotations

from tempestroid.testing.backend import HeadlessBackend, TestBackend, event_schema_for
from tempestroid.testing.locator import Locator, LocatorError
from tempestroid.testing.page import Page
from tempestroid.testing.runner import (
    PLANNED_TARGETS,
    SUPPORTED_TARGETS,
    TestOutcome,
    TestReport,
    run_test_file,
)

__all__ = [
    "Page",
    "Locator",
    "LocatorError",
    "TestBackend",
    "HeadlessBackend",
    "event_schema_for",
    "run_test_file",
    "TestReport",
    "TestOutcome",
    "SUPPORTED_TARGETS",
    "PLANNED_TARGETS",
]
