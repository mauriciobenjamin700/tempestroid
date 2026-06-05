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
    ├── widgets/          # Widget base + Component base + layout.py/inputs.py/media.py/indicators.py (the IR) + events.py
    ├── components/       # composite components (AppBar/Header/Footer/Sidebar/Scaffold/NavBar) — lower to primitives via Component.render
    ├── core/             # ir.py (Node+patches) / reconciler.py (build,diff) / state.py (App) / introspection.py
    ├── renderers/qt/     # renderer + Style→Qt translator + app_runner (run_qt) + simulator + dev_loop
    ├── cli/              # main (tempest dev/spec/build/run/doctor/...) + app_loader + watcher + console (step reporter)
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
| C | Polish: `tempest new`/`build`/`run`/`deploy` + multi-file bundle + stateful hot reload | ✅ done | `tempest new` scaffolds a runnable project; apps are **multi-file** — every device path bundles the whole project tree (`cli/bundle.py`: `resolve_project`/`build_bundle`/`extract_bundle`/`tree_signature`) onto `sys.path` and runs the entry via `spec_from_project`; `tempest build` produces a **standalone shippable APK** via Gradle `assembleDebug` (project baked into the host via `stage_app_bundle`, needs SDK/NDK — verified on device), stamping each app with its **own `applicationId`** (`--app-id`, else derived `com.example.<project>`) so two tempestroid APKs install side by side instead of overwriting each other (`cli/release_build.py`: `build_apk`/`derive_app_id`, sharing `_prepare_gradle_build` with the `--release` AAB; `tempest run` launches `<app-id>/org.tempestroid.host.MainActivity`); `tempest deploy` is the **offline** device push (`deploy_offline`: bundled-host install if needed + one-shot bundle push + launch, no SDK/NDK — verified on device); `tempest run` = build + install + logs; `App.swap_view` powers stateful hot reload — `tempest dev` `r` (save) preserves state via diff, `R` restarts clean, device code-push `reload`s preserving on-device state (all covered by tests) |
| D | Conformance golden snapshots (Qt vs Compose) | ✅ done | `tests/conformance/` pins both `Style` translators: golden snapshots of `to_compose` + `to_qss`/`layout_alignment` for canonical styles (regenerate with `UPDATE_GOLDEN=1`), plus a per-field coverage-parity table that fails if either translator starts/stops handling a field without updating the documented divergences |

### Trilho E — Paridade Flutter/RN (planejado)

Roadmap para fechar o gap com Flutter + React Native. Descritivo fase-a-fase
(IR · Qt · Compose · testes) em [`docs/plan-parity.md`](docs/plan-parity.md).
Toda fase entrega as **três camadas casadas** (IR/diff + renderizador Qt +
renderizador Compose) e só fecha com os **dois renderizadores verdes** + (havendo
device) verificação dual. Sequência: E0 (navegação) destrava multi-tela e é
pré-requisito de quase tudo; E1–E2 são a base de UX; E3 (animação) é consumida por
E0/E2 nas transições; E4–E9 acoplam menos e reordenam por demanda.

| Phase | Scope | Status | Done when |
|---|---|---|---|
| E0 | Navegação e rotas (pilha push/pop, abas, gaveta, botão voltar, deep link) | ✅ done | exemplo de 3 telas navega; voltar do Android faz `pop` (device); abas/gaveta como rotas; transições na conformância |
| E1 | Listas virtualizadas + scroll (lazy, seção sticky, pull-to-refresh, scroll infinito) | ✅ done | lista de 10k itens rola fluido nos dois renderizadores; refresh + `on_end_reached` + cabeçalho fixo |
| E2 | Overlays e feedback (dialog, bottom sheet, toast, tooltip, menu/popover, action sheet) | ✅ done | cada overlay abre/fecha por handler; barrier bloqueia; toast expira; menu ancorado (device) |
| E3 | Framework de animação (controller, tween/curva, implícita, gesto-dirigida, Hero, shimmer) | ✅ done | `Animated`/`AnimatedList`/`Hero`/`Shimmer`/`Skeleton` animam nos dois renderizadores; `AnimationController`/`Tween`/`Spring` testados com clock determinístico; o clock cruza o bridge via `FRAME_TOKEN` (`App._tick_from_device`) e `has_animations` em `MountMessage`/`PatchMessage` liga o `withFrameNanos` no host |
| E4 | Gestos avançados (pan/drag-drop, pinça/zoom, double-tap, dismissible, reorder, viewer) | ✅ done | cada gesto dispara evento tipado e muda estado; swipe-to-delete + reorder (diff) + pinça-zoom (device) |
| E5 | Inputs e formulários (dropdown/select, time, range, form/validação, autocomplete, OTP, máscara) | ✅ done | formulário valida e bloqueia submit inválido com erro por campo nos dois renderizadores |
| E6 | Layout refinado (flex-wrap, pager/carousel, sliver/app bar colapsável, tabela, aspect ratio) | ✅ done | `Wrap` quebra linha igual nos dois renderizadores (conformância `flex_wrap`); `PageView` pagina e emite `PageChangeEvent`; app bar colapsa ao rolar (device) |
| E7 | Mídia e gráficos (vídeo, webview, canvas/desenho, svg, câmera live, QR scanner, mapa, blur, clip) | ✅ done | canvas desenha chart idêntico (lista de comandos JSON na conformância); svg/blur/clip renderizam no device; vídeo/webview via AndroidView; câmera/QR/mapa = placeholder Qt sinalizado, device-only |
| E8 | Plataforma/sistema (haptics, sensores, lifecycle, deep link, permissões, biometria, secure storage, prefs, SQLite, connectivity, push, background) | ✅ done | metade Python unit-testada off-device (envelopes, futures, resultados tipados, parse dos eventos de stream, registros de callback sensor/lifecycle/connectivity, prefs/SQLite reais via tmp_path); tokens reservados `__sensor__`/`__lifecycle__`/`__connectivity__` roteados em jni.py **e** devserver/client.py; `KeyboardAvoidingView` + 4 eventos novos em introspect; biometria/FCM/WorkManager/sensores reais hardware-gated (Kotlin pelo kotlin-specialist). **Device-verificado (2026-06-04, Xiaomi 23053RN02A)** via `examples/platform/app.py` + `examples/sysverify/app.py`: **haptics** (vibração física 80ms via `VibratorManagerService`), **lifecycle** ("foreground"), **prefs** (write), **sensores** (stream do acelerômetro ao vivo, z≈9.8 gravidade, Kotlin `SensorManager`→`__sensor__`→callback→UI), **background/WorkManager** (enqueue confirmado em `dumpsys jobscheduler` `.schedulePersisted()`; worker ainda no-op stub), **biometria** (alcança o `BiometricManager`, retorna resultado tipado — `Status 7`/NONE_ENROLLED sem digital; **fix: `MainActivity` agora é `FragmentActivity`** senão o `BiometricPrompt` não hospeda), **push** (notificação local postada na shade + caminho do token FCM retorna `not_configured` tipado sem `google-services.json`). Pendente só o que exige config externa/hardware extra: digital cadastrada (sucesso pleno da biometria), `google-services.json`+envio server (token/push FCM real), corpo real do worker (re-entrar Python) |
| E9 | Transversais (tema/dark + MediaQuery, i18n/l10n + RTL, acessibilidade/semantics, fontes custom + escala) | ✅ done | metade IR/core completa e testada off-device: `theme.py` (`Theme`/`ThemeMode`/`MediaQueryData`), `i18n.py` (`Locale`/`translate`/`t`), `App.set_theme`/`set_locale`/`_update_media` (contexto que o `view` lê — não nós da árvore, rebuild coalescido), `Semantics`+`focusable`/`focus_order` no `Widget` base (propagados a ambos os renderers + introspect), `Style.text_scale`/`font_asset` nos DOIS tradutores + conformância (goldens `rtl_layout`/`text_scale_font_asset` + parity `(True,True)`), RTL espelha start/end (padding/margin/border-side/text-align) em `to_compose`/`to_qss` via flag `rtl`, `ThemeChangeEvent`/`LocaleChangeEvent` roteados por `THEME_TOKEN`/`LOCALE_TOKEN` em jni.py (sem mudança C/JNI), `examples/theming/app.py`; renderers Qt (E9c) + Compose (E9d) pelos respectivos especialistas. **Device-verificado (2026-06-04, Xiaomi 23053RN02A):** `examples/theming/app.py` → **dark mode** (bg/texto/accent trocam), **i18n/locale** (PT↔árabe via `set_locale`) e **RTL** (texto árabe + espelhamento de start/end) funcionam no aparelho (screenshots light/dark/RTL). TalkBack audível ainda pendente (precisa ativar o leitor) |

**Tudo dentro do projeto — sem projetos extras (enforced).** Toda implementação
do Trilho E (e qualquer feature futura) mora **dentro do repositório
`tempestroid`**: a metade Python no pacote `tempestroid/`, a metade Kotlin/Compose
em `android-host/`. **Nunca** criar repositório, pacote PyPI, plugin ou app
separado para um recurso. O único movimento permitido é (1) **um módulo dedicado
novo** por área para organizar imports (ex.: `navigation.py`, `animation.py`,
`native/sensors.py`), sempre re-exportado pelo `__init__.py` (nunca uma ilha), e
(2) **uma seção de documentação extra** (README/MkDocs). Preferir DIY sobre o que
Qt/Compose/`androidx` já oferecem; dependência externa nova só com justificativa
forte registrada no PR.

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
intent extra. **App files must stay renderer-agnostic — import the Qt renderer
lazily (inside `main()`/`__main__`), never at module top.** A top-level
`from tempestroid.renderers.qt import run_qt` crashes the on-device load (no
PySide6) → white screen. Hardening (2026-06-04): both device entry points
(`run_device_file`/`run_device_bundle` for the baked APK, and the code-push
client) now catch any load/build failure and mount a visible **error screen**
(`bridge/errors.py`, `run_device_error`) carrying the traceback instead of a
blank window; the dev client commits the version hash on a load failure (no
re-fetch storm) and recovers on the next saved edit; `DevServer.do_GET` swallows
`BrokenPipeError`/`ConnectionError`. All verified on device. Native capabilities
(B6) are wired and verified too: `native/`
(`notify` + `send_native`/`native_command`) emits `{"kind":"native"}` envelopes
the host routes via `NativeModules`/`NotificationModule`; a Python `notify()`
posts a real system notification. **All of Trilho B (B0–B6) is implemented and
verified on a real arm64 device.** The `native` envelope + module-router is the
extension point for further capabilities (camera, sensors, …).

**Native capabilities — expanded set (post-B6).** Beyond `notify`, the
`native/` package now exposes geolocation (`get_position`), sharing
(`share`/`share_to_whatsapp`/`open_url`), camera (`take_photo`), device storage
(`read_file`/`write_file`/`delete_file`/`list_files`), clipboard
(`get_text`/`set_text`) and bluetooth (`scan`). This added a **request/response**
shape to the previously fire-and-forget bridge: `send_native_request` ships an
envelope with a `request_id` and `await`s an `asyncio.Future`; the host replies
over the **existing** event channel under the reserved token
`__native_result__:<id>` (`jni._on_event` routes it to `resolve_native_result`),
so **no C/JNI change** was needed. Failures raise `NativeError(code)`. The Kotlin
`NativeModules` is now a per-activity class holding the permission + camera
`ActivityResultLauncher`s. **The Python half (envelopes, future resolution, typed
results) is fully unit-tested off-device (`tests/unit/test_native.py`); the
Kotlin capability modules + manifest perms/FileProvider are written but NOT yet
validated on a device — needs the Android SDK/NDK toolchain (absent in WSL).**

**A2 notes / known limits (revisit post-v1):**

- Child diffing is **positional** by default. When **both** child lists are
  fully keyed with unique keys, a keyed diff runs instead: removed keys →
  `Remove` (descending), survivors realigned with one `Reorder`, added keys →
  `Insert` (ascending final index), matched keys recurse — handling mixed
  insert + remove + reorder in one pass (a pure permutation is the no-add/remove
  case). Partially-keyed / duplicate-key lists still use the positional path.
- Handler props compared by equality → a fresh `lambda` each build reads as a
  prop change. Prefer stable handler references (matters once A4/state lands).

**A3 notes / known limits:**

- `Style → Qt`: padding is QSS for leaves, `contentsMargins` for containers (no
  double-count). `justify`/`align` `START/CENTER/END` → Qt alignment flags;
  `SPACE_*` and `AlignItems.STRETCH` fall through to Qt defaults (post-v1).
  `grow` → layout stretch factor; `width/height` fixed-size is not wired yet.
- `QtRenderer` owns a *host* widget so a root `Replace` is a uniform child swap.
  Updates re-apply the full merged visual idempotently. Headless tests run under
  `QT_QPA_PLATFORM=offscreen` (see `tests/conftest.py`).
- **Navigation hosts (E0b).** `Navigator`/`TabView` render a `QStackedWidget`
  whose *current page's* inner layout is the diffable child slot, so a screen
  swap is the normal child `Replace`, intercepted in `_replace_screen` to add a
  fresh page and animate it in with a one-shot `QPropertyAnimation` (slide
  direction from the `depth` delta, or `fade`/`none` per `transition`); the
  outgoing page is dropped on `finished` and animations are strong-reffed against
  GC. `TabBar`/`TabView` render a tab strip of `QPushButton`s emitting a typed
  `RouteChangeEvent` (`params["index"]`) through `_invoke`. `RouteDrawer` lays
  content + a slide-over panel as direct children (no box layout, like `Stack`),
  sliding the panel on `open`. `Esc` on the simulator host → `App.pop` via the
  `BackKeyFilter` event filter (`app_runner`/`dev_loop`); root pop is a no-op.
  Conformance divergence to document on the Compose side: Qt animates with
  `QPropertyAnimation` vs Compose `AnimatedContent`/`ModalDrawer` — the device
  back button (vs `Esc`) is the Compose/device half (E0c/E0d), not exercised here.
- **Virtualized lists (E1b).** Since the E1 core change `LazyColumn`/`LazyRow`/
  `LazyGrid`/`SectionList` are **not leaves**: `build` materializes the visible
  window into `node.children` (keyed `str(absolute_index)`; sections
  `sec:<title>:header` / `sec:<title>:<index>`). The Qt renderer renders those
  children directly — it no longer self-materializes from `item_count`. The old
  `_LazyArea`/`_LazyGridArea`/`_SectionListArea` auto-materializers are gone.
  `LazyColumn`/`LazyRow`/`SectionList` are `_LazyScrollArea`s whose inner content
  box layout is the diffable child slot, so a window slide (the keyed
  remove/reorder/insert sequence the app produces) flows through the **generic
  container path** unchanged. `LazyGrid` is a `_LazyGridArea` driven like `Stack`
  (no box layout: children re-placed in a `columns`-wide `QGridLayout` via
  `_relayout_grid` on every structural patch). Scroll wiring: the scrollbar's
  `valueChanged` emits a `ScrollEvent(offset)` via `on_scroll`; the **app** turns
  the offset into a new `window` (`App.slide_window`) and rebuilds — the renderer
  never computes the window. Past `end_reached_threshold` → `EndReachedEvent` via
  `on_end_reached`; `refreshing=True` shows a `_RefreshOverlay` busy banner.
  **Qt-vs-Compose divergences (document in the conformance table):** (1) the Qt
  scroll area spans only the *materialized window* (no reserved virtual extent),
  so the scrollbar can only travel within the current window — to scroll further
  the app must already widen the window; Compose's native `LazyColumn` reports
  `layoutInfo` against the full `itemCount`. (2) `SectionList` sticky headers are
  a floated `QLabel` over the viewport top tracking the topmost visible section
  (key prefix `sec:…:header`), vs Compose's intrinsic `stickyHeader`. (3) Desktop
  has no pull-to-refresh gesture → `on_refresh` is driven by the `refreshing`
  prop/overlay only (no pull), vs Compose `PullToRefreshBox`.
- **Overlays + feedback (E2c).** `QtRenderer.mount`/`remount` now take a `Scene`
  (root tree + z-ordered overlay layer); a bare `Node` is still accepted (wrapped
  as an overlay-free `Scene`) for direct-mount tests. Overlay-layer patches carry
  the reserved leading `"overlay"` path token from `diff_scene`: `("overlay",)`
  for layer insert/remove/reorder, `("overlay", i)` for an overlay's own
  update/replace, `("overlay", i, …)` for a within-overlay child patch — the
  renderer strips the `("overlay", i)` prefix and re-bases the patch onto the
  overlay subtree, reusing the generic root-tree machinery (no new patch kind).
  Each overlay node's `barrier` prop drives a shared `_ScrimWidget` (a
  `rgba(0,0,0,0.4)` QWidget over the host that swallows `mousePressEvent` and, on
  tap, dismisses the topmost barrier overlay). Overlay surfaces are top-level
  widgets, not host children: `Dialog`/`BottomSheet`/`Popover` → `_DismissDialog`
  (a `QDialog` that reports user-initiated closes); `Menu`/`ActionSheet` →
  `QMenu` (shown via non-blocking `popup`, **not** `exec`, so the qasync loop
  keeps running; `triggered` → `MenuSelectEvent`); `Toast`/`Tooltip` → a frameless
  floating `QLabel` (toasts fade via `QGraphicsOpacityEffect`+`QTimer` just before
  the **app-side** `loop.call_later` removes them — the Python timer stays
  authoritative). A host-owned dismissal (scrim tap, dialog close, menu select)
  invokes the widget's `on_dismiss`/`on_select` then calls `App.dismiss` via the
  `set_dismiss_overlay` callback (`run_qt`/`Simulator` wire it) — the desktop
  analogue of the device bridge's `__dismiss__:<id>` token; both are idempotent.
  **Qt-vs-Compose divergences (document in the conformance table):** Qt uses
  `QDialog`/`QMenu`/`QTimer`+`QPropertyAnimation` and a manual scrim QWidget;
  Compose uses Material3 `AlertDialog`/`ModalBottomSheet`/`DropdownMenu` which
  manage their own `WindowInsets.safeDrawing` and scrim (no double safe-area
  padding). `BottomSheet` slides up via a `QPropertyAnimation` on `pos` and
  anchors to the host bottom edge; the `Menu`/`Popover` `anchor` key is resolved
  to a global point via a depth-first `key` lookup in the root tree (falling back
  to the host origin when unresolved), vs Compose anchoring by composition.
  Example: `examples/overlays/app.py` (`make run APP=examples/overlays/app.py`).
- **Inputs & forms (E5c).** `Dropdown`→`QComboBox` (`currentIndexChanged`→
  `SelectEvent(value,index)`); `TimePicker`→`QTimeEdit` (inline `HH:mm` spinner,
  `timeChanged`→`TimeChangeEvent`); `RangeSlider`→`_RangeSliderWidget` (two stacked
  `QSlider`s clamped `low<=high`, no native `QRangeSlider`; emits
  `RangeChangeEvent(low,high)` as floats); `Autocomplete`→`QLineEdit`+`QCompleter`
  (two distinct signals — `textChanged`→`TextChangeEvent` via `_value_conns`,
  completer `activated`→`SelectEvent` via the new `_select_conns`); `PinInput`→
  `_PinInputWidget` (N chained one-char `QLineEdit`s with auto focus-advance;
  `TextChangeEvent` per edit + `SubmitEvent` when full); `MaskedInput`→`QLineEdit`
  with `setInputMask` (framework `9`→Qt `0`, `A` kept, other chars escaped if a Qt
  metachar — `_to_qt_input_mask`). `FormField`→`_FormFieldWidget` (a `QVBoxLayout`
  whose middle `content_layout` is the IR child slot, label `QLabel` above + red
  error `QLabel` below, hidden when `error==""`); `Form`→plain `QVBoxLayout`
  container of its `FormField` children — all validation (`Form.validate` →
  `FormState`) runs in Python before patches, so the renderer only renders the
  `error` it is handed and never gates submit. Qt-vs-Compose divergences to pin in
  conformance: `TimePicker` inline spinner vs Compose modal `TimePickerDialog`;
  `RangeSlider` dual `QSlider` vs native M3 `RangeSlider`; `PinInput` chained
  `QLineEdit`s vs `BasicTextField`+`FocusRequester`; `Autocomplete` `QCompleter`
  popup vs filterable `DropdownMenu` — every emitted event payload is identical.
  Example: `examples/forms/app.py` (`make run APP=examples/forms/app.py`).

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
  Run before flipping any phase to ✅ (A–D phases).
- **`android-doctor`** — `bash .claude/skills/android-doctor/check.sh [--quick]`.
  Validates the Trilho B device toolchain (SDK/NDK location, Gradle wrapper
  8.11.1, JDK, connected arm64 device + MIUI gotcha, staged CPython 3.14 +
  wheels) before `make apk`/`install`/`tempest serve`. Resolves the real SDK
  (`/usr/lib/android-sdk`) past the stale env `ANDROID_SDK_ROOT`. `--quick` skips
  the device/adb checks.
- **`dual-verify`** — `bash .claude/skills/dual-verify/verify.sh [APP]`.
  Orchestrates the enforced dual-renderer check: always runs the Qt gate, and if
  `adb` lists a device, runs `android-doctor` + prints the device build/flow/
  screenshot checklist; with no device it prints the mandatory "device half not
  exercised" disclaimer. Run before reporting any framework-surface change done.
- **`parity-phase`** — `bash .claude/skills/parity-phase/plan.sh <E-phase-id>`.
  The Trilho E counterpart of `phase-closer`: prints a phase's spec from
  `docs/plan-parity.md`, resolves its `Arquivos` anchors (edit vs new), checks
  the three-matched-layers invariant (IR + Qt + Compose + conformance), then
  chains `framework-guard` and points at `dual-verify`. Use to start or close any
  E0–E9 sub-task.

Run `framework-guard` + `docs-sync-check` before every commit; `phase-closer`
(A–D) or `parity-phase` (Trilho E) before closing a phase; `android-doctor`
before any Android build and `dual-verify` before calling a framework-surface
change done.

## Workflow

- One phase at a time; close each on its "feito quando" from `docs/plan.md`.
- Keep the phase's tests green before advancing — especially A2 (diff) and D
  (conformance), the backbone of correctness.
- Run `framework-guard` (ruff + `pyright` + `pytest`) before calling a phase done.
- Commits: Conventional Commits (`feat:`, `fix:`, `ref:`, `docs:`, `tests:`,
  `chore:`). Branches: `feat/`, `fix/`, `ref/`.
- **Super PRs + feature grouping allowed. Build agents NEVER self-merge — the
  Claude main thread is the reviewer and fires the review chains; the owner QAs
  post-merge.** Roles:
  - **Group features freely.** A PR may bundle many features / many sub-tasks /
    many thousands of lines. No "one PR per agent" or "one scope per PR" limit —
    ship a coherent batch in one PR when it's convenient.
  - **Build/implementation agents STOP at "done + tested + PR opened".** They do
    NOT merge, do NOT close the loop, do NOT push to `dev`/`main`. They finish the
    work, pass the gate, open the PR against **`dev`** (`gh pr create --base dev`),
    and hand back. (Matches the `parity-chain` skill: it does no git/PR and stops
    for the next stage.) "Tested" is the hard precondition for handoff — see below.
  - **The Claude main thread is the reviewer.** When work comes back green, the
    main thread **fires a review chain** (e.g. `cavecrew-reviewer` / the
    `code-review` skill across the diff) and reads the findings before anything
    merges. Review is the merge bar — not a build agent's say-so. Only after the
    review chain passes does the merge happen. `main` stays the release branch
    reached only by `dev → main`.
  - **"Tested" = the gate is green, no exceptions.** `framework-guard` (ruff +
    `pyright` strict + `pytest` + `mkdocs build --strict`) MUST pass, `docs-sync`
    MUST pass, and the **dual-renderer device verification below** MUST hold when
    a device is attached (Qt + Compose, with the device half exercised). A red or
    skipped gate = NOT tested = NOT eligible for review/merge. Never paper over a
    red gate; fix the cause.
  - **State what was verified in the PR body** — which gates ran, their result,
    and whether the device half was exercised (and if not, say so explicitly).
    The reviewer and the owner both read this.
  - **Branches + Conventional Commits always.** Work on a `feat/`/`fix/`/`ref/`
    branch (a `git worktree` off a clean base when the tree is shared). Branches
    keep history clean and let the owner bisect QA feedback.
  - Before starting, check `origin/main` + open branches so you don't redo landed
    or in-flight work.

## Dual-renderer device verification (enforced)

- **When a physical Android device is connected (`adb devices` lists one), every
  change to framework surface MUST be verified on BOTH renderers before it is
  called done:**
  1. **Qt simulator** — `make run APP=…` / `make dev APP=…` (desktop CPython).
  2. **Kotlin/Compose on the physical device** — `make apk-install` (or
     `tempest serve <app>` over `adb reverse` for live code-push) and exercise
     the changed flow on the real device, confirming with a screenshot.
- Type-check + pytest + the Qt sim are NOT sufficient when a device is attached —
  the Compose renderer and JNI bridge are a separate leaf that only the device
  exercises. A change that passes Qt but is untested on device is incomplete.
- If no device is connected (`adb devices` empty), verify on Qt only and **state
  explicitly** that the device half was not exercised — never claim device
  parity without running on hardware.
- Build prereqs for the device path live in the "Trilho B status" notes above
  (export `ANDROID_SDK_ROOT=/usr/lib/android-sdk`, Gradle wrapper 8.11.1, MIUI
  "Install via USB").

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
