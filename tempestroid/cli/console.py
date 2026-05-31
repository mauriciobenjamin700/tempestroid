"""Step-oriented console reporter for the ``tempest`` CLI.

Gives ``build`` / ``run`` / ``dev`` / ``serve`` a uniform, transparent voice:
each phase is announced as a *step* that resolves to ``✓`` (done) or ``✗``
(failed) with an elapsed time, so a long Gradle build no longer looks frozen.

Output is concise by default — one line per step plus the tool's own stream.
``--verbose`` (``Console(verbose=True)``) echoes the exact command lines and
streams subprocess output live; in concise mode subprocess output is captured
and only a tail is surfaced when the command fails, so the happy path stays
quiet while failures stay actionable.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import IO

__all__ = ["Console", "StepError"]

# Glyphs for the step lifecycle. Kept ASCII-adjacent so they render on a plain
# terminal; the dev loop already uses the same arrows.
_PENDING = "→"
_OK = "✓"
_FAIL = "✗"
_INFO = "•"
_DETAIL = "  ·"
# How many trailing lines of a failed command's output to surface in concise
# mode — enough to show the actual error without dumping the whole build log.
_ERROR_TAIL_LINES = 20


class StepError(RuntimeError):
    """Raised inside a :meth:`Console.step` block to fail it with a message.

    The message is shown on the step's ``✗`` line; the step context manager
    re-raises so callers can still react. Use it for expected, explainable
    failures (missing prerequisite, bad output) rather than letting an opaque
    exception bubble through the step glyph.
    """


class Console:
    """A minimal, dependency-free step reporter for CLI commands.

    Attributes:
        verbose: When ``True``, echo raw command lines and stream subprocess
            output live. When ``False`` (default), keep output concise and only
            surface a failed command's tail.
    """

    def __init__(self, *, verbose: bool = False, stream: IO[str] | None = None) -> None:
        """Initialize the console.

        Args:
            verbose: Enable verbose output (raw commands + live streaming).
            stream: Destination text stream. Defaults to ``sys.stdout``.
        """
        self.verbose: bool = verbose
        self._stream: IO[str] = stream if stream is not None else sys.stdout

    def _write(self, text: str) -> None:
        """Write a line to the stream and flush it.

        Args:
            text: The line to write (a trailing newline is added).
        """
        self._stream.write(text + "\n")
        self._stream.flush()

    def info(self, message: str) -> None:
        """Print an informational line (always shown).

        Args:
            message: The message to print.
        """
        self._write(f"{_INFO} {message}")

    def detail(self, message: str) -> None:
        """Print a secondary line, shown only in verbose mode.

        Args:
            message: The detail to print.
        """
        if self.verbose:
            self._write(f"{_DETAIL} {message}")

    def fail(self, message: str) -> None:
        """Print a standalone failure line (no surrounding step).

        Args:
            message: The failure message.
        """
        self._write(f"{_FAIL} {message}")

    @contextmanager
    def step(self, message: str) -> Generator[None]:
        """Run a unit of work as a reported step.

        Prints a pending line on entry and resolves it to ``✓``/``✗`` with the
        elapsed time on exit. A :class:`StepError` (or any exception) marks the
        step failed and is re-raised.

        Args:
            message: The step description.

        Yields:
            ``None`` — the block runs inside the step.

        Raises:
            Exception: Whatever the block raises, after marking the step failed.
        """
        self._write(f"{_PENDING} {message}")
        started = time.monotonic()
        try:
            yield
        except StepError as exc:
            elapsed = time.monotonic() - started
            self._write(f"{_FAIL} {message} — {exc} ({elapsed:.1f}s)")
            raise
        except BaseException:
            elapsed = time.monotonic() - started
            self._write(f"{_FAIL} {message} ({elapsed:.1f}s)")
            raise
        else:
            elapsed = time.monotonic() - started
            self._write(f"{_OK} {message} ({elapsed:.1f}s)")

    def run_command(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess transparently, honoring the verbosity setting.

        In verbose mode the exact command is echoed and its output streams live.
        In concise mode output is captured; on a non-zero exit the trailing
        :data:`_ERROR_TAIL_LINES` lines are surfaced so the failure is readable
        without dumping the whole log.

        Args:
            cmd: The command and its arguments.
            cwd: Working directory for the subprocess.
            env: Environment for the subprocess.

        Returns:
            The completed process (with captured ``stdout`` in concise mode).

        Raises:
            subprocess.CalledProcessError: If the command exits non-zero.
        """
        if self.verbose:
            joined = " ".join(cmd)
            self.detail(f"$ {joined}" + (f"  (cwd={cwd})" if cwd else ""))
            result = subprocess.run(  # noqa: S603
                list(cmd), cwd=cwd, env=env, check=False, text=True
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, list(cmd))
            return result
        captured = subprocess.run(  # noqa: S603
            list(cmd),
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if captured.returncode != 0:
            self._surface_failure(cmd, captured)
            raise subprocess.CalledProcessError(
                captured.returncode, list(cmd), captured.stdout, captured.stderr
            )
        return captured

    def _surface_failure(
        self, cmd: Sequence[str], result: subprocess.CompletedProcess[str]
    ) -> None:
        """Print the tail of a failed captured command for diagnosis.

        Args:
            cmd: The command that failed.
            result: The completed process holding captured output.
        """
        merged = (result.stdout or "") + (result.stderr or "")
        lines = [line for line in merged.splitlines() if line.strip()]
        tail = lines[-_ERROR_TAIL_LINES:]
        self._write(f"{_FAIL} command failed (exit {result.returncode}): {cmd[0]}")
        if tail:
            self._write(f"  last {len(tail)} line(s) of output:")
            for line in tail:
                self._write(f"    {line}")
        self._write("  re-run with --verbose for the full stream.")
