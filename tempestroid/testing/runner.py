"""Discover and run F9 UI test files against a target backend.

A UI test file is an ordinary tempestroid app module — it defines ``make_state``
and ``view`` (the same contract :mod:`tempestroid.cli.app_loader` enforces for a
runnable app) — plus one or more ``async def test_*(page)`` functions. The runner
loads the module, and for **each** test builds a fresh :class:`Page` over a fresh
backend (so tests never share state), mounts it, runs the coroutine in its own
event loop, and records the outcome.

This slice runs the ``"headless"`` target only: an in-process
:class:`~tempestroid.testing.backend.HeadlessBackend` driving the IR/state/event
core with no renderer. The ``"qt"`` / ``"emulator"`` / ``"device"`` targets are
reserved — they require the stable simulator/emulator/device targets Trilho F8
delivers — and selecting one raises :class:`NotImplementedError` for now.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from tempestroid.testing.backend import HeadlessBackend
from tempestroid.testing.page import Page

__all__ = [
    "TestOutcome",
    "TestReport",
    "run_test_file",
    "SUPPORTED_TARGETS",
    "PLANNED_TARGETS",
]

#: Targets this slice can run.
SUPPORTED_TARGETS: frozenset[str] = frozenset({"headless"})

#: Targets reserved for Trilho F8 (stable simulator/emulator/device). Selecting
#: one raises :class:`NotImplementedError` with a pointer to F8.
PLANNED_TARGETS: frozenset[str] = frozenset({"qt", "emulator", "device"})


def _empty_dump() -> dict[str, Any]:
    """Provide a fresh, typed empty tree dump for the default factory.

    Returns:
        A new empty ``str -> Any`` mapping.
    """
    return {}


def _empty_outcomes() -> list[TestOutcome]:
    """Provide a fresh, typed empty outcome list for the default factory.

    Returns:
        A new empty list of outcomes.
    """
    return []


@dataclass(frozen=True)
class TestOutcome:
    """The result of running one ``test_*`` function.

    Attributes:
        name: The test function's name.
        passed: Whether it completed without raising.
        message: A short failure message (empty when passed).
        traceback: The full traceback on failure (empty when passed).
        tree_dump: A JSON-able dump of the scene at failure (empty when passed).
    """

    name: str
    passed: bool
    message: str = ""
    traceback: str = ""
    tree_dump: dict[str, Any] = field(default_factory=_empty_dump)


@dataclass(frozen=True)
class TestReport:
    """The aggregate result of running every test in a file.

    Attributes:
        path: The test file that was run.
        target: The backend target the tests ran against.
        outcomes: One :class:`TestOutcome` per discovered ``test_*`` function.
    """

    path: str
    target: str
    outcomes: list[TestOutcome] = field(default_factory=_empty_outcomes)

    @property
    def passed(self) -> bool:
        """Whether every test in the file passed.

        Returns:
            ``True`` if all outcomes passed (vacuously true when none ran).
        """
        return all(o.passed for o in self.outcomes)

    @property
    def failures(self) -> list[TestOutcome]:
        """The failing outcomes, if any.

        Returns:
            The outcomes that did not pass (empty when all passed).
        """
        return [o for o in self.outcomes if not o.passed]


def _discover_tests(namespace: dict[str, Any]) -> list[tuple[str, Callable[..., Any]]]:
    """Collect ``test_*`` callables from a module namespace, sorted by name.

    Args:
        namespace: The executed module's namespace.

    Returns:
        ``(name, function)`` pairs for each discovered test, name-sorted.
    """
    return sorted(
        (
            (name, obj)
            for name, obj in namespace.items()
            if name.startswith("test_") and callable(obj)
        ),
        key=lambda item: item[0],
    )


def run_test_file(path: str | Path, target: str = "headless") -> TestReport:
    """Run every ``test_*`` function in a UI test file against a backend.

    Loads the file's ``make_state``/``view`` plus its tests, then runs each test
    with a fresh :class:`Page` over a fresh backend in its own event loop. A test
    that raises (an :class:`AssertionError`, a :class:`TimeoutError`, anything)
    is recorded as a failure with its traceback and the failing scene dump; other
    tests still run.

    Args:
        path: Path to the UI test file (an app module + ``test_*`` functions).
        target: The backend target — only ``"headless"`` is supported in this
            slice.

    Returns:
        The :class:`TestReport` with one outcome per test.

    Raises:
        NotImplementedError: If ``target`` is a planned (F8) target.
        ValueError: If ``target`` is unknown.
        FileNotFoundError: If ``path`` does not exist.
        AttributeError: If the file lacks ``view`` or ``make_state``.
    """
    if target in PLANNED_TARGETS:
        raise NotImplementedError(
            f"target {target!r} arrives with Trilho F8 (stable simulator/"
            "emulator/device targets). Only the headless target is supported "
            "today."
        )
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"unknown target {target!r}; supported: {sorted(SUPPORTED_TARGETS)}"
        )

    file = Path(path).resolve()
    if not file.is_file():
        raise FileNotFoundError(f"UI test file not found: {file}")

    make_state, view, tests = _load_test_module(file)
    outcomes: list[TestOutcome] = []
    for name, func in tests:
        outcomes.append(_run_one(name, func, make_state, view))
    return TestReport(path=str(file), target=target, outcomes=outcomes)


def _load_test_module(
    file: Path,
) -> tuple[Callable[[], Any], Callable[..., Any], list[tuple[str, Callable[..., Any]]]]:
    """Exec a UI test file and pull its app contract + ``test_*`` functions.

    Puts the file's parent directory on ``sys.path`` first, so a test file can
    re-use a sibling app module (``from app import view, make_state``) regardless
    of where the project's ``pyproject.toml`` sits. The file must define ``view``
    and ``make_state`` (the runnable-app contract).

    Args:
        file: The resolved UI test file path.

    Returns:
        A ``(make_state, view, tests)`` triple.

    Raises:
        AttributeError: If the file lacks ``view`` or ``make_state``.
        TypeError: If ``view`` or ``make_state`` is not callable.
    """
    parent = str(file.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # Register the throwaway module in sys.modules before exec so decorators that
    # resolve `sys.modules[cls.__module__]` (e.g. @dataclass on a state class)
    # work; reloads overwrite the same name on purpose (mirrors app_loader).
    module = ModuleType(file.stem)
    module.__file__ = str(file)
    sys.modules[file.stem] = module
    source = file.read_text(encoding="utf-8")
    exec(compile(source, str(file), "exec"), module.__dict__)  # noqa: S102
    namespace: dict[str, Any] = module.__dict__

    if "view" not in namespace or "make_state" not in namespace:
        raise AttributeError(
            f"{file} must define `view(app)` and `make_state()` (re-export them "
            "from the app module under test)"
        )
    view = namespace["view"]
    make_state = namespace["make_state"]
    if not callable(view) or not callable(make_state):
        raise TypeError(f"{file}: `view` and `make_state` must be callable")
    return make_state, view, _discover_tests(namespace)


def _run_one(
    name: str,
    func: Callable[..., Any],
    make_state: Callable[[], Any],
    view: Callable[..., Any],
) -> TestOutcome:
    """Run a single test coroutine on a fresh page + loop, capturing the outcome.

    Args:
        name: The test function name.
        func: The (async) test function taking a single ``page`` argument.
        make_state: The app's state factory.
        view: The app's view function.

    Returns:
        The :class:`TestOutcome` for this test.
    """
    page = Page(HeadlessBackend(make_state, view))

    async def _body() -> None:
        await page.mount()
        result = func(page)
        if inspect.iscoroutine(result):
            await result

    loop = asyncio.new_event_loop()
    # Make this the active loop so any sync code reaching for the running/policy
    # loop (App._loop's fallback, fixtures) sees the same one we drive.
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_body())
        return TestOutcome(name=name, passed=True)
    except BaseException as exc:  # noqa: BLE001 — capture any test failure
        # Snapshot the *actual* failing page so the dump shows the state the
        # assertion saw, not a fresh remount.
        dump: dict[str, Any] = {}
        try:
            dump = page.snapshot()
        except BaseException:  # noqa: BLE001 — best-effort dump
            dump = {}
        return TestOutcome(
            name=name,
            passed=False,
            message=f"{type(exc).__name__}: {exc}",
            traceback="".join(traceback.format_exception(exc)),
            tree_dump=dump,
        )
    finally:
        loop.close()
        asyncio.set_event_loop(None)
