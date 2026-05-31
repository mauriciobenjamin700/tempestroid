"""A dependency-free async file watcher (mtime polling).

Polls a set of files/directories on an interval and fires a callback when any
``.py`` file's modification time changes. Polling (rather than ``watchdog`` or
inotify) keeps the dev loop dependency-light and works uniformly across WSL,
which is the primary dev environment.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

__all__ = ["snapshot_mtimes", "watch"]


def _iter_py_files(paths: list[Path]) -> list[Path]:
    """Expand watched paths into the concrete ``.py`` files to track.

    Args:
        paths: Files and/or directories to watch.

    Returns:
        The ``.py`` files under those paths (the file itself if it is a file).
    """
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        elif path.suffix == ".py":
            files.append(path)
    return files


def snapshot_mtimes(paths: list[Path]) -> dict[Path, float]:
    """Capture the current modification times of all watched ``.py`` files.

    Args:
        paths: Files and/or directories to watch.

    Returns:
        A mapping of file path to modification time. Files that vanish mid-read
        are skipped.
    """
    mtimes: dict[Path, float] = {}
    for file in _iter_py_files(paths):
        try:
            mtimes[file] = file.stat().st_mtime
        except OSError:
            continue
    return mtimes


async def watch(
    paths: list[Path],
    on_change: Callable[[], Awaitable[None]],
    *,
    interval: float = 0.3,
) -> None:
    """Poll watched files and invoke ``on_change`` whenever one changes.

    Runs until cancelled. Exceptions raised by ``on_change`` are allowed to
    propagate to the caller's task so they are not silently swallowed.

    Args:
        paths: Files and/or directories to watch.
        on_change: Async callback fired once per detected change batch.
        interval: Poll interval in seconds.
    """
    previous = snapshot_mtimes(paths)
    while True:
        await asyncio.sleep(interval)
        current = snapshot_mtimes(paths)
        if current != previous:
            previous = current
            await on_change()
