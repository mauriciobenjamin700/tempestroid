#!/usr/bin/env python
"""docs-sync-check — verify README.md tracks the live framework.

Checks three kinds of drift and exits non-zero on any:

1. Public exports (``tempestroid.__all__``) vs. names mentioned in README.
2. ``tempest`` CLI subcommands (from the argparse parser) vs. README CLI table.
3. Phase status rows agreeing between README.md and CLAUDE.md.

Run from the repo root::

    uv run python .claude/skills/docs-sync-check/check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

failed = False


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{BOLD}==> {title}{RESET}")


def fail(msg: str) -> None:
    """Record a failure and print it."""
    global failed
    failed = True
    print(f"{RED}FAIL{RESET}  {msg}")


def ok(msg: str) -> None:
    """Print a passing line."""
    print(f"{GREEN}PASS{RESET}  {msg}")


def read(path: Path) -> str:
    """Read a text file relative to repo root."""
    return (ROOT / path).read_text(encoding="utf-8")


def check_exports(readme: str) -> None:
    """Cross-check ``tempestroid.__all__`` against README mentions."""
    section("exports ⨉ README")
    import tempestroid

    exported: list[str] = [n for n in tempestroid.__all__ if not n.startswith("__")]
    missing = [n for n in exported if n not in readme]
    if missing:
        fail("exported names absent from README Public API: " + ", ".join(missing))
    else:
        ok(f"all {len(exported)} public exports appear in README")


def check_cli(readme: str) -> None:
    """Cross-check registered CLI subcommands against the README CLI table."""
    section("CLI ⨉ README")
    from tempestroid.cli.main import app

    # `version` aliases the global `--version`/`-V` flag and isn't part of the
    # README command table, so it's excluded from the cross-check.
    commands: set[str] = {
        info.name
        for info in app.registered_commands
        if info.name and info.name != "version"
    }
    if not commands:
        fail("could not introspect any CLI subcommands")
        return
    missing = sorted(c for c in commands if f"tempest {c}" not in readme)
    if missing:
        fail("CLI commands missing from README table: " + ", ".join(missing))
    else:
        ok(
            f"all {len(commands)} CLI commands appear in README: "
            + ", ".join(sorted(commands))
        )


_PHASE_ROW = re.compile(r"^\|\s*(A\d|B0–B6|C\s*/\s*D)\s*\|.*?\|.*?(✅|⬜)")


def phase_statuses(text: str) -> dict[str, str]:
    """Extract ``{phase_id: '✅'|'⬜'}`` from a markdown phase table."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _PHASE_ROW.match(line.strip())
        if m:
            out[m.group(1).replace(" ", "")] = m.group(2)
    return out


def check_phases(readme: str, claude: str) -> None:
    """Compare phase status between README and CLAUDE.md."""
    section("phase tables (README ⨉ CLAUDE.md)")
    r = phase_statuses(readme)
    c = phase_statuses(claude)
    shared = sorted(set(r) & set(c))
    if not shared:
        fail("no comparable phase rows found in both files")
        return
    mismatch = [p for p in shared if r[p] != c[p]]
    if mismatch:
        for p in mismatch:
            fail(f"phase {p}: README={r[p]} but CLAUDE.md={c[p]}")
    else:
        ok(f"{len(shared)} shared phases agree on status")


def main() -> int:
    """Run all sync checks and return a process exit code."""
    readme = read(Path("README.md"))
    claude = read(Path("CLAUDE.md"))
    check_exports(readme)
    check_cli(readme)
    check_phases(readme, claude)
    section("summary")
    if failed:
        print(f"{RED}docs-sync-check: FAIL{RESET}")
        return 1
    print(f"{GREEN}docs-sync-check: PASS{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
