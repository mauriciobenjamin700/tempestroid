---
name: phase-closer
description: Validate a tempestroid roadmap phase's "done when" before marking it ✅. Runs the quality gates, the docs-sync check, and prints the phase's done-when criterion from docs/plan.md / CLAUDE.md so it can be verified honestly. Use when about to close a phase (A0–A6, B0–B6, C, D) or when asked "is phase X done".
---

# phase-closer

A phase is only done when its "feito quando" / "done when" is backed by green
tests and the docs reflect it. This skill enforces that gate so a phase is never
marked ✅ on vibes.

## When to use

- Right before flipping a phase row to ✅ in `CLAUDE.md` / `README.md`.
- When the user asks "can we close phase X?" or "is X done?".

## How to run

```bash
bash .claude/skills/phase-closer/close.sh <phase-id>
# e.g.
bash .claude/skills/phase-closer/close.sh B2
```

The script:

1. Prints the phase's **done-when** criterion (the row from the `CLAUDE.md`
   phase table) and its `docs/plan.md` description, so you can confirm scope.
2. Runs **framework-guard** (ruff + pyright + pytest + conventions).
3. Runs **docs-sync-check** (README ⨉ exports ⨉ CLI ⨉ phase tables).
4. Prints a checklist for the human/agent to confirm the done-when is actually
   met (the automated gates prove the code is healthy, not that the *feature*
   exists — that judgment stays with you).

It exits non-zero if any automated gate fails.

## Closing a phase (after the script is green)

1. Confirm the done-when criterion is genuinely satisfied — point to the
   specific test(s) that back it.
2. Flip the status in **both** the `CLAUDE.md` phase table and the `README.md`
   status table (docs-sync-check enforces they agree).
3. Update `docs/plan.md` if its phase notes need it.
4. Commit with a Conventional Commit (`feat:` / `docs:`), referencing the phase.

Never mark a phase done if a gate is red or the done-when is only partially met
— say so plainly instead.
