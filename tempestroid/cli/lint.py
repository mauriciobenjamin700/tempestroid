"""Quality-gate helpers backing ``tempest lint`` / ``fix`` / ``format`` / etc.

These wrap the tools an app project uses — ``ruff`` (lint + format),
``pyright`` (type check) and ``pytest`` — so a tempestroid app gets the same
one-command quality gate the framework itself runs, without the user memorizing
the underlying invocations. Each runner resolves the tool from the active
environment (directly on ``PATH``, else via ``uv run``), so it works whether or
not the project's virtualenv is activated.
"""

from __future__ import annotations

import shutil
import subprocess

import typer

__all__ = [
    "run_full_check",
    "run_pyright",
    "run_pytest",
    "run_ruff_check",
    "run_ruff_fix",
    "run_ruff_format",
]


def _resolve(executable: str) -> list[str] | None:
    """Return an argv prefix invoking ``executable``, or ``None`` when absent.

    Preference order: the tool directly on ``PATH`` (an activated venv / global
    install), else ``uv run <executable>`` when ``uv`` is available (handles a
    project-local virtualenv without activation).

    Args:
        executable: The command name (``ruff`` / ``pyright`` / ``pytest``).

    Returns:
        The argv prefix to extend with extra arguments, or ``None`` when no
        runner could be found.
    """
    direct = shutil.which(executable)
    if direct is not None:
        return [direct]
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "run", executable]
    return None


def _execute(executable: str, args: list[str]) -> int:
    """Run ``executable args`` and return its exit code.

    Args:
        executable: The command to run.
        args: Extra arguments to forward verbatim.

    Returns:
        The child process exit code, or ``127`` when neither the executable nor
        ``uv`` is available.
    """
    argv = _resolve(executable)
    if argv is None:
        typer.echo(
            f"error: {executable!r} is not on PATH and uv is unavailable. "
            "Install it (or activate the project venv) and retry.",
            err=True,
        )
        return 127
    return subprocess.call([*argv, *args])


def run_ruff_check(target: str) -> int:
    """Invoke ``ruff check <target>``.

    Args:
        target: The path passed verbatim to ruff.

    Returns:
        The ruff exit code.
    """
    return _execute("ruff", ["check", target])


def run_ruff_fix(target: str, *, unsafe: bool = False) -> int:
    """Apply every automatic ruff fix, then format the target.

    Runs two passes so the formatter sees the rewritten file: ``ruff check
    --fix [--unsafe-fixes] <target>`` then ``ruff format <target>``. Both passes
    always run — ``ruff check --fix`` exits non-zero on any residual violation it
    cannot autofix even after rewriting, so short-circuiting would skip the
    formatter. The lint exit code is surfaced afterwards so CI still fails on the
    leftovers.

    Args:
        target: The path passed verbatim to ruff.
        unsafe: When ``True``, also pass ``--unsafe-fixes``.

    Returns:
        ``0`` when both passes succeed with nothing left to fix; otherwise the
        lint pass exit code (residual violations), or the format pass exit code
        when the lint pass was clean.
    """
    check_args = ["check", "--fix"]
    if unsafe:
        check_args.append("--unsafe-fixes")
    check_args.append(target)
    check_code = _execute("ruff", check_args)
    format_code = _execute("ruff", ["format", target])
    return check_code or format_code


def run_ruff_format(target: str, *, check: bool) -> int:
    """Invoke ``ruff format`` (write, or check-only).

    Args:
        target: The path passed verbatim to ruff.
        check: When ``True``, run ``ruff format --check`` (read-only).

    Returns:
        The ruff exit code.
    """
    args = ["format"]
    if check:
        args.append("--check")
    args.append(target)
    return _execute("ruff", args)


def run_pyright(target: str) -> int:
    """Invoke ``pyright <target>``.

    Args:
        target: The path passed verbatim to pyright.

    Returns:
        The pyright exit code.
    """
    return _execute("pyright", [target])


def run_pytest(target: str | None) -> int:
    """Invoke ``pytest`` with an optional target.

    Args:
        target: Optional pytest path filter. ``None`` runs the default suite.

    Returns:
        The pytest exit code.
    """
    args = [target] if target else []
    return _execute("pytest", args)


def run_full_check(target: str) -> int:
    """Run the entire quality gate sequentially.

    Order: ``ruff check`` → ``ruff format --check`` → ``pyright`` → ``pytest``.
    Stops at the first non-zero exit code so failures surface fast.

    Args:
        target: The path inspected by ruff/pyright. Pytest always runs against
            the project's configured ``testpaths``.

    Returns:
        The first non-zero exit code, or ``0`` when every gate passed.
    """
    steps: list[tuple[str, list[str]]] = [
        ("ruff", ["check", target]),
        ("ruff", ["format", "--check", target]),
        ("pyright", [target]),
        ("pytest", []),
    ]
    for executable, args in steps:
        joined = " ".join(args)
        typer.echo(f"$ {executable} {joined}", err=True)
        code = _execute(executable, args)
        if code != 0:
            return code
    return 0
