# Roadmap and phases

Development follows two base tracks and one expansion track. **Track A** is the
pure-Python framework (desktop/CPython). **Track B** is the Android runtime
(CPython 3.14 + Kotlin host + JNI bridge + Compose renderer). **Track E** is
parity with Flutter/React Native (planned). The full plan is in
[Design plan (EN)](plan.md) and, for Track E, in
[Parity plan](plan-parity.md).

## Track A — framework (pure Python)

| Phase | Scope | Status |
|---|---|---|
| A0 | Foundation: package, tooling, `tempest --help` | ✅ |
| A1 | Style model + typed widget primitives | ✅ |
| A2 | Reconciler: `build → diff → patch` | ✅ |
| A3 | Qt renderer: patches → `QWidget`s, `Style → Qt` | ✅ |
| A4 | Async event loop: asyncio ⨉ Qt (`qasync`) | ✅ |
| A5 | `tempest dev`: watcher, hot restart, command loop | ✅ |
| A6 | Typed event contract + introspection | ✅ |

## Track B — Android runtime

All of Track B (B0–B6) is **implemented and verified on a real arm64 device**
(Xiaomi `23053RN02A`, Android 15).

| Phase | Scope | Status |
|---|---|---|
| B0 | CPython 3.14 for arm64 | ✅ |
| B1 | Native wheels (pydantic-core) + device site-packages | ✅ |
| B2 | Kotlin host: embed CPython, boot the interpreter off the UI thread via JNI | ✅ |
| B3 | JNI bridge (native): bidirectional Python↔Kotlin transport | ✅ |
| B4 | Compose renderer (native): render the serialized tree, apply patches, route taps | ✅ |
| B5 | Dev server + QR (LAN code-push + log relay) | ✅ |
| B6 | Native capabilities (notifications) | ✅ |

## Polish and conformance

| Phase | Scope | Status |
|---|---|---|
| C | Polish: `new`/`build`/`run` + stateful hot reload | ✅ |
| D | Conformance golden snapshots (Qt vs Compose) | ✅ |

!!! note "Conformance suite (phase D)"
    `tests/conformance/` pins both `Style` translators: golden snapshots of
    `to_compose` + `to_qss`/`layout_alignment` for canonical styles (regenerate
    with `UPDATE_GOLDEN=1`), plus a per-field coverage-parity table that fails if
    either translator starts (or stops) handling a field without updating the
    documented divergences.

## Native capabilities — expanded set (post-B6)

Beyond `notify`, the `native/` package already exposes geolocation
(`get_position`), sharing (`share`/`share_to_whatsapp`/`open_url`), camera
(`take_photo`), device storage (`read_file`/`write_file`/`delete_file`/
`list_files`), clipboard (`get_text`/`set_text`) and bluetooth (`scan`).

This added a **request/response** shape to the bridge (previously fire-and-forget):
`send_native_request` ships an envelope with a `request_id` and `await`s an
`asyncio.Future`; the host replies over the **same** event channel under the
reserved token `__native_result__:<id>` — **no C/JNI change**. Failures raise
`NativeError(code)`.

!!! warning "Device validation pending"
    The Python half (envelopes, future resolution, typed results) is **fully
    unit-tested off-device** (`tests/unit/test_native.py`). The Kotlin capability
    modules + manifest perms/`FileProvider` are **written but not yet validated on
    a device** — they need the Android SDK/NDK toolchain.

## Track E — Flutter / React Native parity (planned)

Roadmap to close the gap with what Flutter + RN ship out of the box. Every phase
delivers the **three matched layers** (IR/diff + Qt renderer + Compose renderer)
and closes only with **both renderers green** + (when a device is present) dual
verification. Phase-by-phase spec in [Parity plan](plan-parity.md).

**Sequence.** E0 (navigation) unblocks multi-screen and is a prerequisite for
almost everything; E1–E2 are the UX base; E3 (animation) is consumed by E0/E2 in
transitions; E4–E9 couple less and reorder on demand (except E6c←E1 and E3d←E0).

| Phase | Scope | Core risk | Status |
|---|---|---|---|
| E0 | Navigation and routes (push/pop stack, tabs, drawer, back button, deep link) | low (reuses diff) | 🔜 |
| E1 | Virtualized lists + scroll (lazy, sticky section, pull-to-refresh, infinite scroll) | medium (windowed diff) | 🔜 |
| E2 | Overlays and feedback (dialog, bottom sheet, toast, tooltip, menu, action sheet) | **high** (`Scene` + namespaced `Path`) | 🔜 |
| E3 | Animation framework (controller, tween/curve, implicit, gesture, Hero, shimmer) | **high** (frame clock) | 🔜 |
| E4 | Advanced gestures (pan/drag-drop, pinch/zoom, double-tap, dismissible, reorder) | low (pattern ready) | 🔜 |
| E5 | Inputs and forms (dropdown, time, range, form/validation, autocomplete, OTP, mask) | low | 🔜 |
| E6 | Refined layout (flex-wrap, pager/carousel, collapsing app bar, table, aspect ratio) | low | 🔜 |
| E7 | Media and graphics (video, webview, canvas, svg, live camera, QR, map, blur, clip) | medium (canvas IR) | 🔜 |
| E8 | Platform/system (haptics, sensors, lifecycle, permissions, biometrics, storage, SQLite, push) | low (B6 pattern + stream token) | 🔜 |
| E9 | Cross-cutting (theme/dark + MediaQuery, i18n/RTL, accessibility, custom fonts + scale) | medium (context + RTL) | 🔜 |

!!! info "Everything inside the project — no extra projects"
    All Track E work lives **inside the `tempestroid` repository**: the Python
    half in the `tempestroid/` package, the Kotlin/Compose half in
    `android-host/`. Never create a separate repo, PyPI package, plugin, or app.
    The only allowed move is a **new dedicated module** per area (e.g.
    `navigation.py`, `animation.py`), always re-exported from `__init__.py`.

## Maintenance — quality skills (`.claude/skills/`)

Framework-health guards, chained by the gates:

| Skill | Command | Role |
|---|---|---|
| `framework-guard` | `make gate` (`check.sh [--quick]`) | ruff + pyright (strict) + pytest + `mkdocs build --strict` + convention heuristics |
| `docs-sync-check` | `make docs-sync` | README ↔ live exports ↔ CLI commands ↔ phase tables |
| `phase-closer` | `close.sh <phase>` | validate an A–D phase's "done when" before flipping it ✅ |
| `android-doctor` | `make doctor` (`check.sh [--quick]`) | validate the Track B toolchain: SDK/NDK, Gradle wrapper 8.11.1, JDK, arm64 device + MIUI gotcha, staged runtime |
| `dual-verify` | `make dual-verify` (`verify.sh [APP]`) | enforced dual check: Qt gate + (with a device) Compose build/flow/screenshot |
| `parity-phase` | `make parity PHASE=…` (`plan.sh <E-id>`) | the Track E counterpart of `phase-closer`: phase spec + three-layer invariant + gate |

## Open follow-ups

- **Validate the expanded native capabilities on device:** the Kotlin modules for
  geo/share/camera/storage/clipboard/bluetooth must be exercised on a real device
  (run `make doctor` → `make apk-install` → `dual-verify`).
- **Inputs on device (Compose):** the Kotlin renderer still falls back to an empty
  box for some input widgets; the matching cases need to grow on the host. In the
  Qt simulator these widgets already work.
- **Start Track E with E0 (navigation):** prerequisite for almost everything;
  begin with the core sub-task (`E0a`) via `make parity PHASE=E0`.
