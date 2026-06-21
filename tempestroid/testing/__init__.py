"""tempestroid.testing — a Playwright-style UI test driver for the native IR.

The driver automates an app the way Playwright automates a web page, but against
the framework's **renderer-agnostic IR** rather than a DOM: it mounts an app,
locates nodes by stable key / visible text / accessibility semantics, injects the
same typed events a real tap or keystroke produces, and asserts the resulting UI
state — with **auto-wait** built into every action and assertion (the tree must
settle before proceeding; no fixed sleeps), so timing flake disappears.

Because every backend speaks the same IR + typed-event vocabulary, one test
script runs against every target. Two backends ship today: the **headless**
backend (:class:`HeadlessBackend`) drives the
:class:`~tempestroid.core.state.App`/IR/event core in-process with no renderer,
exercising the full ``event → handler → state → rebuild → diff → patch`` loop
deterministically; the **emulator** backend (:class:`EmulatorBackend`) drives a
REAL app through the **Compose** renderer on an Android emulator over the dev-
server harness bridge, and :class:`EmulatorPool` runs N isolated emulators in
parallel. The :class:`Page`/:class:`Locator`/assertion surface is identical
across targets, so **the same test runs headless and on the emulator** — only the
handler resolution differs (headless → callable, emulator → token).

Public surface:

* :class:`Page` — the top-level driver (locators, actions, auto-waiting asserts).
* :class:`Locator` — a lazy, late-resolving node query.
* :class:`TestBackend` — the protocol a renderer target implements.
* :class:`HeadlessBackend` — the no-renderer reference backend.
* :class:`EmulatorBackend` — drives a real Compose render on an emulator/device.
* :class:`EmulatorPool` — allocate/recycle N isolated emulators for parallel runs.
* :func:`allocate_adb_server_port` / :func:`current_adb_server_port` — per-agent
  adb-server isolation (a private ``ANDROID_ADB_SERVER_PORT`` per agent) so
  parallel agents never contend on — nor wedge — the shared default server.
* :func:`run_test_file` — load + run a UI test file's ``test_*`` functions.
* :func:`run_test_files_emulator` — shard files across emulator serials.
* :mod:`tempestroid.testing.mirror` — host-side scene mirror (deserialize +
  apply patches), re-exported here as :func:`deserialize_scene` /
  :func:`apply_patches`.
"""

from __future__ import annotations

from tempestroid.testing.adb_server import (
    allocate_adb_server_port,
    current_adb_server_port,
)
from tempestroid.testing.backend import HeadlessBackend, TestBackend, event_schema_for
from tempestroid.testing.emulator import EmulatorBackend
from tempestroid.testing.locator import Locator, LocatorError
from tempestroid.testing.mirror import (
    apply_patches,
    deserialize_node,
    deserialize_scene,
)
from tempestroid.testing.page import Page
from tempestroid.testing.pool import (
    EmulatorPool,
    max_parallel_emulators,
    running_emulators,
)
from tempestroid.testing.runner import (
    PLANNED_TARGETS,
    SUPPORTED_TARGETS,
    TestOutcome,
    TestReport,
    run_test_file,
    run_test_file_emulator,
    run_test_files_emulator,
)

__all__ = [
    "Page",
    "Locator",
    "LocatorError",
    "TestBackend",
    "HeadlessBackend",
    "EmulatorBackend",
    "EmulatorPool",
    "max_parallel_emulators",
    "running_emulators",
    "allocate_adb_server_port",
    "current_adb_server_port",
    "event_schema_for",
    "deserialize_node",
    "deserialize_scene",
    "apply_patches",
    "run_test_file",
    "run_test_file_emulator",
    "run_test_files_emulator",
    "TestReport",
    "TestOutcome",
    "SUPPORTED_TARGETS",
    "PLANNED_TARGETS",
]
