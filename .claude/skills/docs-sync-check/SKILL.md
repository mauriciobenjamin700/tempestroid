---
name: docs-sync-check
description: Verify README.md is in sync with the framework — public exports (tempestroid.__all__), the tempest CLI commands, and the phase status tables across README / CLAUDE.md / docs/plan.md. Use after changing public API, CLI commands, or a phase status, and to enforce the CLAUDE.md "Documentation sync" rule.
---

# docs-sync-check

`README.md` is the project's public face and must always reflect the current
framework (the "Documentation sync (enforced)" rule in `CLAUDE.md`). This skill
catches drift between the code and the docs.

## When to use

- After adding/changing public exports in any `__init__.py`.
- After adding/changing a `tempest` CLI command or flag.
- After opening/closing a phase.
- As a pre-commit / pre-PR check that docs weren't forgotten.

## How to run

```bash
uv run python .claude/skills/docs-sync-check/check.py
```

It reports drift in three areas and exits non-zero if any is found:

1. **Exports ⨉ README** — every name in `tempestroid.__all__` (read live by
   importing the package) should appear in `README.md`'s Public API section.
   Flags exports missing from the README and README-documented names no longer
   exported.
2. **CLI ⨉ README** — every subcommand registered in `tempestroid.cli.main`'s
   parser should appear in the README CLI table, and vice versa.
3. **Phase tables** — the phase rows in `README.md` and `CLAUDE.md` must agree
   on status (✅ / ⬜) for each phase id.

## Interpreting failures

- **Missing export in README** → add it to the matching Public API subsection
  (Style / Widgets / Events / Core / Introspection / Renderer).
- **Stale README name** → the export was removed or renamed; update the README.
- **CLI drift** → update the README CLI table (command + status).
- **Phase mismatch** → reconcile the status in README and CLAUDE.md; also check
  `docs/plan.md` reflects reality.

Fix the docs (or the code) until the check is green before reporting the change
complete. This check is heuristic (substring presence), so a green result means
"named somewhere", not "documented well" — still read the diff.
