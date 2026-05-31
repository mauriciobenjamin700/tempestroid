---
name: parity-phase
description: Scaffold and gate a Trilho E (Flutter/RN parity) phase or sub-task — prints its spec from docs/plan-parity.md (Arquivos/Contrato/Sub-tarefas/Feito quando), checks the "three matched layers" invariant (IR/diff + Qt translator + Compose translator + conformance + tests), and chains framework-guard + dual-verify so a phase closes only with BOTH renderers green. Use when starting/closing an E phase (E0–E9 or sub-tasks E0a…), or when asked to "plan E-phase X" / "run parity-phase".
---

# parity-phase

Every Trilho E phase ships its surface in **three matched layers** and closes
only with **both renderers green** (the rule in `docs/plan-parity.md` §0):

1. **IR / diff** — Pydantic widget + event in `tempestroid/` (reconciler stays
   agnostic).
2. **Qt translator/renderer** — `renderers/qt/` (desktop simulator).
3. **Compose translator/renderer** — `renderers/compose/` + `android-host/…`
   (device).
4. **Conformance** — any new `Style` field is mirrored in both translators with
   a `tests/conformance/` entry.

A phase that touches only one renderer, or skips conformance for a new `Style`
field, is **not done**. This skill surfaces the phase's exact spec and walks the
gate so nothing is half-landed.

## When to use

- Starting an E phase / sub-task — to load its `Arquivos` / `Contrato` /
  `Sub-tarefas` / `Feito quando` without re-reading the whole plan.
- Closing one — to run the matched-layers + dual-renderer gate before flipping
  its status (the E counterpart of `phase-closer`, which targets A–D).
- When asked to "plan E0", "scaffold the parity phase", or "run parity-phase".

## How to run

```bash
bash .claude/skills/parity-phase/plan.sh <phase-id>
# e.g.  parity-phase plan.sh E0      (whole phase)
#       parity-phase plan.sh E2a     (a sub-task — prints the parent phase spec)
```

The script:

1. **Prints the phase spec** — extracts the `## E<n> — …` section from
   `docs/plan-parity.md` (Descrição → Superfície nova → Arquivos → Contrato →
   Sub-tarefas → Metas → Feito quando).
2. **Resolves the `Arquivos` anchors** — for each path the phase lists, reports
   whether it exists (edit) or is new (create), so the work-list is concrete.
3. **Three-layer presence check** — greps the phase's listed Python/Kotlin/test
   anchors and warns if a renderer leg or the conformance entry looks untouched
   relative to the others (heuristic — read the diff, it only flags obvious gaps).
4. **Chains the gates** — `framework-guard` (Python) then prints the
   `dual-verify` command for the on-renderer check.

It exits non-zero if `framework-guard` fails.

## The matched-layers rule (what the script enforces in spirit)

When you implement an E sub-task, every layer it spans must land together:

- New widget → re-export in `widgets/__init__.py` **and** `tempestroid/__init__.py`
  (both `__all__`), per the template in `plan-parity.md` §0.1.
- New event → frozen `Event` in `widgets/events.py`, in the widget's
  `event_schemas`, validated by `parse_event`, mapped in `event_type_for` if it
  crosses the bridge → appears in `introspect()` (`tempest spec`).
- New `Style` field → **both** `style_translator.py` files + a `tests/conformance/`
  golden, with any intended Qt↔Compose divergence documented in the Trilho D table.
- Native capability → B6 pattern (`{"kind":"native"}` + `NativeModules` Kotlin +
  `__native_result__:<id>`), **no C/JNI change** unless a new stream channel needs
  a reserved token (flag it in the "feito quando").

## Closing an E phase

1. Confirm the phase's **Feito quando** is genuinely met — name the backing
   tests (unit + conformance) and, with a device attached, the on-device
   evidence (screenshot).
2. Run `dual-verify` — both renderers green (or, no device, state the device
   half was not exercised).
3. Flip the phase row in **both** the `CLAUDE.md` Trilho E table and `README.md`,
   and update `docs/plan-parity.md` notes; run `docs-sync-check`.
4. Commit (Conventional Commits), one PR scoped to the sub-task.

Never close an E phase on one renderer alone — say plainly which leg is missing.
