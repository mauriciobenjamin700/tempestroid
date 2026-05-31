---
name: dual-verify
description: Orchestrate the enforced dual-renderer verification — Qt simulator (desktop CPython) AND Kotlin/Compose on a connected arm64 device — before a framework-surface change is called done. Decides which path applies (device connected → both; no device → Qt only, stated explicitly), runs the right commands, and prints the manual screenshot/flow checklist. Use after changing IR/widgets/Style/renderers, before reporting a change done, or when asked to "verify on both renderers" / "run dual-verify".
---

# dual-verify

The CLAUDE.md "Dual-renderer device verification (enforced)" rule: a change to
framework surface is **not done** until it is verified on **both** leaf
renderers when a device is attached — the Qt simulator AND Kotlin/Compose on a
real arm64 device. Type-check + pytest + the Qt sim alone are insufficient,
because the Compose renderer + JNI bridge are a separate leaf only the device
exercises. This skill picks the correct path and walks it honestly.

## When to use

- After any change to framework surface: IR/widgets (`tempestroid/widgets/`),
  the reconciler (`core/`), either `Style` translator (`renderers/qt/`,
  `renderers/compose/`), the bridge, or native capabilities.
- Right before reporting such a change complete.
- Closing a Trilho E phase (every E phase ships the three layers matched and
  closes only with **both renderers green**).
- When the user asks to "verify on both", "check device parity", or
  "run dual-verify".

## How to run

```bash
# APP defaults to examples/counter/app.py — override APP=path/to/app.py
bash .claude/skills/dual-verify/verify.sh [APP]
```

The script:

1. Runs **android-doctor --quick** then `adb devices` to decide the path.
2. **Always** runs the Qt leg: `framework-guard` (gates) — the Qt sim itself is
   interactive, so the script *prints* the exact `make run APP=…` /
   `make dev APP=…` command for you to run and eyeball, and reminds you to
   screenshot it.
3. **If a device is connected**, prints the device leg commands
   (`make apk-install` for a full APK, or `tempest serve <app>` over
   `adb reverse` for live code-push) and the on-device flow + screenshot
   checklist. Runs `android-doctor` (full) first so the build won't fail
   mid-Gradle.
4. **If no device**, prints the mandatory disclaimer to state explicitly that
   the device half was NOT exercised — never claim parity without hardware.

## The two legs (what you must actually do)

The script orchestrates and gates; **you** perform the visual confirmation:

- **Qt simulator** — `make run APP=…` (or `make dev APP=…` for hot restart).
  Exercise the changed flow; confirm layout + interactivity; take a screenshot.
- **Compose on device** — `make apk-install` (rebuild+install) or
  `tempest serve <app>` (live code-push, no rebuild). Exercise the *same* flow on
  the real device; confirm it matches; **confirm with a screenshot** (the rule
  requires it). Watch `make logcat` for runtime errors.

## Known device-render gotchas to check for

From prior on-device testing (carry these as a checklist):

- Buttons must honor the `Style` background — a Material-purple button means the
  Compose translator dropped the bg color.
- Dense/operator-key layouts can collapse — verify spacing/arrangement on device,
  not just in Qt.
- The dev-client can hit localhost DNS flakiness — prefer `adb reverse` + an
  explicit host when code-push stalls.

## Reporting

- **Both green** → state which flow you exercised on each renderer and attach/
  reference both screenshots.
- **Qt only (no device)** → say plainly: "device half NOT exercised — no device
  connected; verified on Qt only." Do not imply parity.
- **Either red** → the change is incomplete; report the failing leg with its
  output, don't summarize it away.
