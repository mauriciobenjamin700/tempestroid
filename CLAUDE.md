# CLAUDE.md — tempestroid

Framework for building **native Android apps** in **typed Python**. A declarative,
typed widget tree (Pydantic IR) is diffed by a shared reconciler into patches;
two leaf renderers apply them — **Qt** (desktop simulator) and **Jetpack
Compose** (device). This is a **framework, not a web service**: no FastAPI,
SQLAlchemy, Redis, or HTTP-server layering. See [`docs/plan.md`](docs/plan.md)
for the full design and phase roadmap.

## Stack

- **Core model:** Pydantic v2 (style + widget IR).
- **Simulator:** PySide6 / Qt, with `qasync` to fuse asyncio into the Qt loop
  (optional extra `qt`; phases A3/A4).
- **Bridge (phase B):** **hand-rolled JNI** over the CPython C-API (NOT pyjnius /
  Chaquopy / python-for-android) — decided after research, for full toolchain
  control on unpatched CPython.
- **Packaging (phase B):** Gradle + a minimal Kotlin host embedding **official
  CPython 3.14** (PEP 738; official Android binary releases), modelled on the
  CPython `Platforms/Android/testbed`. Native wheels (`pydantic-core`) via
  **cibuildwheel ≥ 3.4**.
- Python `>=3.11`. The Android runtime targets **CPython 3.14** (PEP 738 Tier 3);
  Trilho A is pure desktop CPython.

**Trilho B research (read before starting B):** `docs/research/android-runtime.md`
(findings + primary sources) and `docs/research/android-runbook.md` (executable
B0–B6 with exact commands/versions/done-when). Needs an Android SDK/NDK host —
not runnable in this WSL session without the toolchain.

## Layout

```text
tempestroid/
├── docs/research/        # Trilho B web research + executable runbook (read before B)
├── toolchain/            # B0/B1 build scripts: fetch CPython 3.14 + cibuildwheel wheels
├── android-host/         # B2–B4 Gradle/Kotlin host skeleton (embeds official CPython via JNI)
└── tempestroid/          # the framework (Trilho A, pure Python) — flat layout, package at repo root
    ├── style.py          # Style + value objects (Color/Edge/Border/SideBorder/Corners/Shadow/Gradient/Transition) + enums (Pydantic, frozen)
    ├── widgets/          # Widget base + layout.py/inputs.py/media.py/indicators.py (the IR) + events.py
    ├── core/             # ir.py (Node+patches) / reconciler.py (build,diff) / state.py (App) / introspection.py
    ├── renderers/qt/     # renderer + Style→Qt translator + app_runner (run_qt) + simulator + dev_loop
    ├── cli/              # main (tempest dev/spec/...) + app_loader + watcher
    ├── renderers/compose/# Style→Compose translator (Python side ✓; Kotlin renderer = B4)
    ├── bridge/           # serialize IR/patches, handler registry+dispatch, DeviceApp (Python ✓; JNI transport = B3)
    ├── native/           # capability modules: notifications, camera         (phase B6)
    └── devserver/        # LAN code push + log relay                         (phase B5)
```

Create packages only when a phase needs them — no empty placeholders. The
`android-host/` + `toolchain/` trees are intentional B-track scaffolding (Gradle/
Kotlin/C + shell), not Python packages, so the Python quality gates don't touch
them; they don't build in this WSL session (need Android SDK/NDK).

## Conventions (enforced)

- **Strings:** double quotes everywhere. Never single quotes.
- **Typing:** every parameter, return, and annotation fully typed (explicit
  `Any` when unavoidable). `pyright` in strict mode must pass.
- **Docstrings:** Google style, in **English**, on every module/class/function.
  Explanatory inline comments may be PT-BR.
- **Imports:** absolute from `tempestroid`; import at the module level, never from
  submodules. Every `__init__.py` re-exports its public surface and keeps
  `__all__` current.
- **Async-first:** the core assumes an asyncio loop. Handlers and lifecycle hooks
  may be sync or `async`; prefer async APIs, wrap native callbacks as awaitables,
  use structured concurrency for task lifecycle. In Qt, integrate via `qasync`.
- **Collections:** return `[]` for "no matches", never raise. List fields default
  via `Field(default_factory=list)`, never `list[X] | None = None`.
- **Naming:** files `snake_case`; classes `PascalCase`; functions/vars
  `snake_case`; constants `UPPER_SNAKE_CASE`. Widgets are bare nouns (`Text`,
  `Column`); style enums are `PascalCase`.
- **Pydantic models** are frozen where they represent immutable values (`Style`,
  `Color`, `Edge`, `Border`) so the reconciler can diff by value.

## Phase status

Tracks `docs/plan.md`. Update the table when a phase opens/closes; keep the
"done when" honest (it must be backed by green tests).

| Phase | Scope | Status | Done when |
|---|---|---|---|
| A0 | Foundation: package, `pyproject`, tooling, `tempest --help` | ✅ done | editable install + CLI respond; lint/type-check run |
| A1 | Style model + typed widget primitives | ✅ done | tree builds, validates, type-checks clean |
| A2 | Reconciler: `build → diff → patch` (insert/remove/update/reorder/replace) | ✅ done | diff unit tests produce the correct patch list |
| A3 | Qt renderer: apply patches to `QWidget`s; `Style → Qt` (QBoxLayout + QSS) | ✅ done | example app renders in a Qt window from the tree |
| A4 | Async event loop: asyncio ⨉ Qt (`qasync`); event → handler → state → coalesced rebuild → diff → patch | ✅ done | an `async` handler that `await`s updates the screen without freezing UI |
| A5 | `tempest dev` (sim): file watcher, hot restart, command loop (r/R/s/q) | ✅ done | edit `app.py` + `R` restarts the sim with new UI |
| A6 | Typed contract + introspection at the boundary | ✅ done | typed round-trip with validation + structured error |
| B0 | CPython 3.14 for arm64 | ✅ done | official `python-3.14.5-aarch64-linux-android` → `toolchain/dist/python/arm64-v8a/` (libpython3.14.so verified ARM aarch64) |
| B1 | Native wheels (pydantic-core) + device site-packages | ✅ done | `pydantic_core-2.41.5-cp314-android_24_{arm64_v8a,x86_64}.whl` via cibuildwheel 3.4.1; `toolchain/02_stage_deps.sh` assembles site-packages (pydantic 2.12.5 + the Android wheel + deps); on-device `import pydantic` + `import tempestroid` + `build`/`serialize_node` round-trip → `rc=0` |
| B2 | Kotlin host: embed CPython, extract stdlib + site-packages, boot interpreter off-UI-thread via JNI | ✅ done | APK boots CPython 3.14 on an arm64 device and runs the framework: `import pydantic`/`import tempestroid` + `build`/`serialize_node` → `python exited rc=0` (verified on Xiaomi `23053RN02A`, Android 15) |
| B3 | JNI bridge (native): bidirectional Python↔Kotlin transport | ✅ done | on-device round-trip: `run_device` mounts a counter → `JniBridge`→`send_to_host`→`onMessageFromPython` (mount); injected `dispatchEvent("1:on_click")` → event sink → `handle_event` → `set_state` → patch back up (`count=0`→`count=1`), interpreter stays live |
| B4 | Compose renderer (native): render the serialized tree, apply patches, route taps | ✅ done | on-device: Compose renders the mount tree (Text/Button/Column + style spec → Modifier/Arrangement), applies patch batches (recomposes), and a real button tap → `dispatchEvent` → handler → patch → UI updates (`count` 0→4 by tapping; verified by screenshot) |
| B5 | dev server + QR (LAN code-push + log relay) | ✅ done | on-device: `tempest serve <app>` (over `adb reverse`) pushes the app source; the device's code-push client polls, fetches, re-execs and hot-restarts the `DeviceApp` — editing+saving the file live-reloaded the device UI without an APK rebuild (verified by screenshot) |
| B6 | native capabilities (notifications) | ✅ done | on-device: a `notify()` call from a Python handler → `native` command over the bridge → `NativeModules`/`NotificationModule` → a system notification posts (verified via `dumpsys notification` + the shade). The `native` envelope + module-router is the template for further capabilities (camera, etc.) |
| C | Polish: `tempest new`/`build`/`run` + stateful hot reload | ✅ done | `tempest new` scaffolds a runnable project; `tempest build`/`run` stage the app as an asset + drive the `android-host` Gradle wrapper + `adb` (need SDK/NDK); `App.swap_view` powers stateful hot reload — `tempest dev` `r` (save) preserves state via diff, `R` restarts clean, device code-push `reload`s preserving on-device state (all covered by tests; build/run device path needs the toolchain) |
| D | Conformance golden snapshots (Qt vs Compose) | ✅ done | `tests/conformance/` pins both `Style` translators: golden snapshots of `to_compose` + `to_qss`/`layout_alignment` for canonical styles (regenerate with `UPDATE_GOLDEN=1`), plus a per-field coverage-parity table that fails if either translator starts/stops handling a field without updating the documented divergences |

**Trilho B status:** research done (`docs/research/`), decisions fixed (CPython
3.14 official + hand-rolled JNI + cibuildwheel + Compose DIY). **B0/B1/B2 are
validated on a real arm64 device** (2026-05-30): the `android-host/` APK
builds (Gradle wrapper **8.11.1** — the env's global Gradle 9.5 is incompatible
with AGP 8.7), bundles `libpython3.14.so` + `libtempest_host.so` + the full
CPython stdlib, extracts it on first launch, and boots the interpreter off the
UI thread to `rc=0`. Build prereqs on this host: Android SDK/NDK live at
`/usr/lib/android-sdk` (NOT the stale `ANDROID_HOME`), so export
`ANDROID_SDK_ROOT=/usr/lib/android-sdk`; the device is Xiaomi/MIUI and needs
**"Install via USB"** enabled or `adb install` fails `INSTALL_FAILED_USER_RESTRICTED`.
Two AGP gotchas the host build works around: the global Gradle 9.5 is too new for
AGP 8.7 (use the bundled wrapper 8.11.1), and AGP's default `ignoreAssetsPattern`
contains `<dir>_*` which silently drops asset dirs starting with `_` (e.g.
`pydantic/_internal/`) — overridden in `app/build.gradle.kts`.
**The device-independent halves of B3/B4 are implemented and tested in pure
Python:**

- `renderers/compose/` — `to_compose(style)` emits a serializable Compose spec
  (mirrors `Style → Qt`; the pair feeds the phase-D conformance suite).
- `bridge/` — `serialize_node`/`serialize_patch` lower the IR/patches to JSON-able
  dicts (handlers → path **tokens**, style → Compose spec); `HandlerRegistry`
  resolves tokens and **validates payloads via `parse_event`** before dispatch;
  `DeviceApp` wires `App` to an abstract `Bridge` (`LoopbackBridge` for tests) —
  the device-side analogue of `run_qt`. Event round-trip + coalesced patch send
  are covered by tests.

The JNI transport (B3 native) is **done and verified on device**: `tempest_host.c`
registers a built-in `_tempest_host` module (`send_to_host` + `set_event_sink`)
and a `dispatchEvent` JNI entry; `PythonRuntime.kt` exposes `dispatchEvent` +
`onMessageFromPython` + a settable `messageSink`; `bridge/jni.py` provides
`JniBridge` + `run_device`. The Compose renderer (B4 native) is **done and
verified on device**: `TempestTree.kt` parses the mount/patch envelopes into a
snapshot-state node tree; `TempestRenderer.kt` renders it (`Style → Compose` spec
→ `Modifier`/`Arrangement`/`Alignment`) and routes taps back via `dispatchEvent`;
`MainActivity` is a `ComponentActivity` whose `messageSink` feeds the tree. The
dev server + QR (B5 native loop) is **done and verified on device**: `devserver/`
holds the `DevServer` (serves source + relays logs), `run_dev_client`/
`serve_device` (the device poll-fetch-restart loop), and `render_qr`; `tempest
serve <app>` drives it, and `MainActivity` enters dev mode on a `tempest_dev_url`
intent extra. Native capabilities (B6) are wired and verified too: `native/`
(`notify` + `send_native`/`native_command`) emits `{"kind":"native"}` envelopes
the host routes via `NativeModules`/`NotificationModule`; a Python `notify()`
posts a real system notification. **All of Trilho B (B0–B6) is implemented and
verified on a real arm64 device.** The `native` envelope + module-router is the
extension point for further capabilities (camera, sensors, …).

**A2 notes / known limits (revisit post-v1):**

- Child diffing is **positional** by default; a single `Reorder` is emitted only
  for a *pure* permutation (both lists fully keyed, unique keys, same set, equal
  length). Mixed insert+reorder falls back to positional — correct, less optimal.
- Handler props compared by equality → a fresh `lambda` each build reads as a
  prop change. Prefer stable handler references (matters once A4/state lands).

**A3 notes / known limits:**

- `Style → Qt`: padding is QSS for leaves, `contentsMargins` for containers (no
  double-count); `margin` is a QSS box-model rule (always emitted, no conflict
  with padding). `justify`/`align` `START/CENTER/END` → Qt alignment flags;
  `SPACE_BETWEEN/AROUND/EVENLY` are realized in the renderer with stretch spacers
  (`_sync_main_axis` re-lays children around spacers; structural patches strip
  spacers first so a child's IR index still maps to its layout slot).
  `AlignItems.STRETCH` is Qt's default cross-axis fill (no flag set). `grow` →
  layout stretch factor; fixed `width`/`height`/`aspect_ratio` →
  `setFixedWidth`/`setFixedHeight` in the renderer (`aspect_ratio` derives the
  missing dimension from the fixed one; with neither fixed it has no Qt anchor
  and is left to the device — a documented divergence).
- Text features beyond QSS live on a custom `_TextLabel(QLabel)`: `text_align` →
  `setAlignment`; `max_lines`/`text_overflow`/`line_height` → a `QTextLayout`
  paint that caps lines, elides the last visible line on `ELLIPSIS`, and uses
  `line_height` as a leading multiplier. Plain text (none of those set) falls
  back to the stock `QLabel` paint untouched.
- `QtRenderer` owns a *host* widget so a root `Replace` is a uniform child swap.
  Updates re-apply the full merged visual idempotently. Headless tests run under
  `QT_QPA_PLATFORM=offscreen` (see `tests/conftest.py`).

**A4 notes / known limits:**

- `App[S]` (in `core/state.py`) is renderer-agnostic: it owns state, builds via
  the `view(app) -> Widget` function, diffs, and hands patches to an
  `apply_patches` callback. `view` receives the app (read `app.state`, wire
  handlers to `app.set_state`) — no circular dependency.
- Rebuilds are **coalesced**: `request_rebuild` schedules one `_rebuild` via
  `loop.call_soon`; many `set_state` in a tick → one diff. No-op rebuilds emit
  no patches.
- `run_qt` (in `renderers/qt/app_runner.py`) fuses asyncio into Qt via `qasync`
  so handlers can `await`. The `QtRenderer` schedules coroutine handlers as loop
  tasks and holds strong refs until done (structured cancellation on unmount is
  post-v1). `qasync` ships no type stubs → one scoped `# pyright: ignore`.
- Example: `examples/counter/app.py` — `uv run python examples/counter/app.py`.

**A5 notes / known limits:**

- App-file contract (for `tempest dev`): the module must expose `view(app) ->
  Widget` and `make_state() -> S`. `cli/app_loader.py` compiles/execs the file
  fresh each load (no `.pyc` reuse) so reloads always see the latest edit.
- `cli/watcher.py` is a dependency-free mtime poller (works on WSL); `tempest dev`
  auto-restarts on save **and** on the `r`/`R` command. v1 is **hot restart**
  (clean state) only — stateful hot reload is post-v1.
- `run_dev` (in `renderers/qt/dev_loop.py`) runs one qasync loop driving the
  window + watcher + line-based stdin commands (`r`/`R`/`s`/`q`). A bad save is
  caught and printed; the loop survives. Qt is imported lazily by the CLI so
  `tempest --help` works without the `qt` extra.
- Run it: `uv run tempest dev examples/counter/app.py`.

**A6 notes / known limits:**

- Typed events live in `widgets/events.py`: `Event` base + `TapEvent` /
  `TextChangeEvent` (frozen Pydantic). `parse_event(event_type, raw)` is the
  boundary gate — validates a raw payload into a typed event or raises
  `EventValidationError` carrying the structured (JSON-serializable) field errors.
  This is the Python↔Kotlin contract the device bridge (phase B) will use.
- Widgets declare their event contract via the `event_schemas` classvar (e.g.
  `Button.event_schemas == {"on_click": TapEvent}`).
- `core/introspection.py` publishes the `/docs`-style contract: `introspect()`
  → `{"widgets": {...prop schemas + events...}, "events": {...payload schemas}}`,
  fully JSON-serializable. `EventHandler` carries a `WithJsonSchema` annotation
  so handler-bearing widgets don't break schema generation. CLI: `tempest spec`.

**Tooling note:** the `qt` deps (PySide6, qasync) are in the **dev dependency
group** (not just the `qt` extra), so `uv sync` / `uv run` install them for
local work without `--extra qt`. `uv`'s `[tool.uv] default-extras` is NOT
supported on the pinned uv (0.7.4) — don't reintroduce it (it warns on every
command). End users still get the simulator via `pip install tempestroid[qt]`.

## Architecture invariants

- The **reconciler is renderer-agnostic** — pure data in, patches out. All
  platform divergence is confined to the two `Style` translators.
- A **widget tree is the IR**: serializable Pydantic models. Walk any tree via
  `Widget.child_nodes()`; never reach into renderer-specific child storage.
- Python runs on a **background thread hosting an asyncio loop**, never the UI
  thread. Marshalling crosses a single bridge boundary.

## Documentation sync (enforced)

`README.md` is the project's public face — it must always reflect the current
framework. **Whenever you add or change framework surface, update `README.md` in
the same change.** This triggers on:

- New/changed public exports in `tempestroid/__init__.py` (or any package's
  `__init__.py` public surface) → update the **Public API** section.
- New/changed widgets, style enums, events, patches, or core types → update the
  matching API subsection.
- New/changed `tempest` CLI commands or flags → update the **CLI** table.
- A phase opening/closing → update the **Status** table (keep it in sync with
  the phase table in this file).
- New examples, install steps, or layout changes → update the relevant section.

Keep `README.md`, the phase table here, and `docs/plan.md` consistent. A code
change that alters public behavior without a matching README update is
incomplete.

## Maintenance skills (`.claude/skills/`)

Project skills that guard framework health — use them, don't reinvent the checks:

- **`framework-guard`** — `bash .claude/skills/framework-guard/check.sh [--quick]`.
  Runs ruff + pyright (strict) + pytest + `mkdocs build --strict` (when
  `mkdocs.yml` exists) + convention heuristics (quotes, typing, `__all__`, no
  empty packages). The maintenance gate. `--quick` skips pytest + the docs build.
- **`docs-sync-check`** — `uv run python .claude/skills/docs-sync-check/check.py`.
  Verifies README.md tracks live exports (`tempestroid.__all__`), the `tempest`
  CLI commands, and that phase tables in README/CLAUDE.md agree. Enforces the
  "Documentation sync" rule above.
- **`phase-closer`** — `bash .claude/skills/phase-closer/close.sh <phase-id>`.
  Prints a phase's done-when, runs both gates above, and a manual checklist.
  Run before flipping any phase to ✅.

Run `framework-guard` + `docs-sync-check` before every commit; `phase-closer`
before closing a phase. (Android-toolchain validation skill — `android-doctor` —
arrives with track B.)

## Workflow

- One phase at a time; close each on its "feito quando" from `docs/plan.md`.
- Keep the phase's tests green before advancing — especially A2 (diff) and D
  (conformance), the backbone of correctness.
- Run `framework-guard` (ruff + `pyright` + `pytest`) before calling a phase done.
- Commits: Conventional Commits (`feat:`, `fix:`, `ref:`, `docs:`, `tests:`,
  `chore:`). Branches: `feat/`, `fix/`, `ref/`.
- **One PR per agent, scoped to its own work.** When multiple agents work in
  parallel, each agent opens **exactly one** PR containing **only what it did and
  validated** — never bundle another agent's changes, and never commit to or
  update a PR that belongs to another agent. Each agent works on its **own
  branch** (a dedicated `git worktree` off a clean base is the safe way when the
  working tree is shared), so a tree-wide change reconstructed from that base
  never drags in another agent's uncommitted work. Before starting, check
  `origin/main` and open PRs/branches so you don't reimplement work already
  landed or in flight. It is fine to keep a branch local and push it later.

## Commands

**Prefer the `Makefile` at the repo root** — it wraps every recurring task
(gates, run/dev, docs, package build, release with tag, Android APK build/install).
Run `make` (or `make help`) to list targets. Use these instead of retyping raw
`uv run …` / Gradle / adb lines. Raw equivalents below for reference.

```bash
make help        # list every target
# quality gates
make gate        # full framework-guard: ruff + pyright(strict) + pytest + conventions + docs
make quick       # fast gate (no pytest)
make lint        # ruff check          | make format → ruff --fix + format
make typecheck   # pyright (strict)    | make test → pytest
make docs-sync   # README/CLI/phase-table sync check
# run / dev (APP=examples/counter/app.py by default; override APP=…)
make run         # run an app in the Qt simulator
make dev         # tempest dev: simulator + hot restart
make spec        # print the typed contract as JSON
# docs site
make docs-build  # mkdocs build --strict   | make docs-serve → live preview
# package + release
make build       # uv build → sdist + wheel in dist/
make bump        # bump pyproject version (PART=patch|minor|major, default patch)
make release     # runs gate + docs-sync, requires clean tree, tags v<version> + pushes → PyPI publish CI
# android (Trilho B — needs Android SDK/NDK + connected arm64 device)
make toolchain   # fetch CPython 3.14 + build wheels + stage device site-packages
make apk         # Gradle assembleDebug   | make install → adb installDebug | make apk-install → both
make logcat      # tail device logs       | ANDROID_SDK_ROOT defaults to /usr/lib/android-sdk
make clean       # remove build/test/cache artifacts
```

Release flow: `make bump PART=…` → commit → `make release` (verifies gates +
clean tree, refuses an existing tag, then tags `v<version>` and pushes; the tag
push triggers `.github/workflows/publish.yml` → PyPI Trusted Publishing).

Raw equivalents (no Makefile):

```bash
uv sync                                   # installs core + dev group (incl. Qt sim)
uv run tempest --help
uv run tempest spec                       # print the typed contract as JSON
uv run tempest dev examples/counter/app.py  # interactive simulator + hot restart
uv run python examples/counter/app.py     # run the counter directly
uv run ruff check .
uv run pyright
uv run pytest
```
