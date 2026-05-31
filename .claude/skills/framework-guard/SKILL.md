---
name: framework-guard
description: Run tempestroid's quality gates (ruff + pyright strict + pytest) and convention checks (double quotes, full typing, Google docstrings, __init__ re-exports). Use before closing a phase, before a commit, or when asked to validate the framework / check conventions / "garantir manutenção do framework".
---

# framework-guard

Validate that the tempestroid framework still meets its enforced standards. This
is the maintenance gate: if it fails, the framework is broken and a phase cannot
be closed.

## When to use

- Before marking any phase done (pairs with `phase-closer`).
- Before any commit that touches `src/tempestroid/`.
- When the user asks to "validate", "check conventions", "run the gates", or
  "ensure framework maintenance".

## How to run

Run the bundled script from the repo root:

```bash
bash .claude/skills/framework-guard/check.sh
```

It runs, in order, and reports a single PASS/FAIL summary:

1. `uv run ruff check .` — lint + import order + quote style + docstring rules
   (ruff config in `pyproject.toml` selects `E,F,I,UP,B,Q,ANN,D`).
2. `uv run pyright` — strict-mode type check (`typeCheckingMode = "strict"`).
3. `uv run pytest` — the full test suite (`asyncio_mode = "auto"`).
4. Convention heuristics ruff cannot catch (see below).

Pass `--quick` to skip pytest (lint + types + conventions only) for a fast loop.

## What the script checks beyond ruff/pyright/pytest

- **Single quotes** in `src/` string literals → must be double quotes.
- **Empty placeholder packages** — a package dir with only `__init__.py` and no
  sibling modules (the layout rule forbids empty placeholders).
- **`__init__.py` re-export hygiene** — every package `__init__.py` must define
  `__all__`.

## Interpreting failures

- **ruff** → fix the reported lines; never blanket-`# noqa`. Quote, typing
  (`ANN`), and docstring (`D`) violations are framework conventions, not style
  nits.
- **pyright** → the project is strict; `Any` must be explicit, no implicit
  `Optional`. The one sanctioned `# pyright: ignore` is `qasync` (no stubs) —
  do not add more without justification.
- **pytest** → a red test means the phase regressed. Fix the code, not the test,
  unless the test encodes the wrong contract.
- **convention heuristics** → fix at the source; these mirror the rules in
  `CLAUDE.md` "Conventions (enforced)".

Report the exact failing command output to the user; do not summarize away the
error text.
