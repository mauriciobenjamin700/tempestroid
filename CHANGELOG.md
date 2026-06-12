# Changelog

All notable changes to **tempestroid** are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Dropped `material-icons-extended` (~9 MB DEX, Trilho F4 trim sub-task 5,
  cut #1).** The Compose host now depends on `androidx.compose.material:material-icons-core`
  instead of `…-extended`. The only consumer, `iconFor()` in `TempestRenderer.kt`,
  maps 22 names to `Icons.Filled.*` glyphs that **all ship in the core set**
  (transitive via `material3`), and the real source of truth for an icon is the
  SVG `iconPath` prop inlined by `tempestroid/icons.py` — so no `-extended`-only
  glyph was ever referenced and the swap is behavior-neutral. **Measured A/B
  (same host, lean `assembleDebug`):** the debug APK drops **49.5 MB → 46.8 MB
  (−2.71 MB)** and the uncompressed DEX **60.7 MB → 29.0 MB (−31.7 MB)** —
  **11,106 fewer classes** (27,625 → 16,519), of which **10,130 are icon glyphs**
  (10,375 → 245, the residual 245 being the curated core set the renderer maps to).
  This was the largest non-CPython block left in the lean build after
  feature-gating; the earlier ~9 MB estimate in the design doc understated it. The
  compressed-APK win (−2.71 MB) is smaller than the uncompressed-DEX win because
  icon-vector bytecode compresses heavily. **On-device verification (icons still
  render) pending — no device on this host.** Design:
  `docs/research/feature-gating.md` ("Próximos cortes" #1).

### Added

- **Opt-in native features (APK trim, Trilho F4 sub-task 5).** The heavy Android
  capabilities (CameraX, ML Kit barcode, Firebase/FCM, media3 video, maps) are now
  **gated at build time** — the lean default APK ships none of them, cutting the
  debug APK from **~58 MB to ~47 MB (−11.4 MB)** and the uncompressed DEX by
  ~11.9 MB (verified: the lean DEX has 0 classes from camera/mlkit/media3/
  firebase, the full DEX has 4,913). An app opts back in per feature via
  `[tool.tempest] features = ["camera", "qr"]` or `tempest build --feature camera`
  (repeatable); `qr` transitively pulls in `camera`. Each opt-in builds from source
  (SDK/NDK); the lean default keeps the toolchain-free prebuilt-host path. A
  gated-off widget (`CameraPreview`/`QrScanner`/`VideoPlayer`/`MapView`) renders a
  labeled placeholder and a gated-off native capability returns a typed
  `NativeError("feature_not_built")`. New `FEATURES`/`resolve_features` in
  `cli/project.py`; the `-Ptempest.features` Gradle property gates the deps +
  source sets + a configuration-time manifest generator in `android-host`. Mirror
  PyPI extras (`tempestroid[camera]` …) document intent. Further trim (the
  ~9 MB `material-icons-extended`, R8 minification) is future work. Design:
  `docs/research/feature-gating.md`. **On-device verification pending (no device).**

## [0.12.1] — 2026-06-11

### Documentation

- Every core enum member (layout/style/event/native) and the `Border` class now
  carries a Google-style `Attributes:` docstring that explains what the member
  means and when it applies — replacing absent or circular descriptions.

### Changed

- Ran `ruff format` + autofix across the package to clear pre-existing formatting
  debt; no behaviour change (pyright clean, 1119 tests green).
- `tempest build --fast` rejection message uses backticks around the target name
  instead of single quotes (avoids a convention-guard false positive).

## [0.12.0] — 2026-06-10

### Added

- **Adaptive launcher icons** (Trilho F4, sub-task 2). `tempest icon <src>
  --adaptive` also writes `ic_launcher_foreground.png` (the mark centered with
  the adaptive safe-zone margin), and `tempest build --adaptive-icon <fg.png>
  --icon-bg <#rrggbb>` emits a real Android adaptive icon — staging
  `res/drawable/ic_launcher_foreground.png` + `res/values/ic_launcher_background.xml`
  + `res/mipmap-anydpi-v26/ic_launcher{,_round}.xml` so the launcher applies its
  mask (rounded/squircle) on API 26+, with the square PNG (`--icon`) as the
  pre-26 fallback. Reads `adaptive_icon`/`icon_bg` from `[tool.tempest]` too. Like
  `--icon`, it is Gradle-only (a compiled resource) and `--fast` warns + keeps the
  default. The branding stager now tracks and removes the files/dirs it creates so
  the host tree is left untouched.
- **`tempest build release-apk` — release-signed standalone APK** (Trilho F4,
  sub-task 1). The professional-distribution counterpart of `tempest build apk`
  (debug-signed) and `tempest build prd` (store AAB): drives Gradle
  `assembleRelease` with the publisher's keystore (`--keystore`, else an
  auto-generated cached one), producing `dist/<project>-release.apk` installable
  outside the Play Store (a website, an alternative store, a direct link) and
  verifiable with `apksigner verify`. Unlike the debug `apk`, it does **not** fall
  back to the toolchain-free `--fast` repackage — a release-signed APK requires
  the real build. New `build_release_apk` in `cli/release_build.py` (sharing
  `ReleaseConfig` / `ensure_release_keystore` / the new `_signing_props` helper
  with `build_aab`) + the `release-apk` target in `cli/main.py`.

### Documentation

- **Renderer-coverage matrix** (Trilho F4, sub-task 3). New bilingual reference
  page `docs/referencia/cobertura.md` (PT + EN, in the MkDocs nav) mapping every
  widget to its Qt-simulator and Compose-device handler. Grounded in the Kotlin
  `when (node.type)` dispatch (`TempestRenderer.kt`): every exported primitive has
  a handler in both renderers (Compose: 62 primitive + 7 overlay cases; composites
  are lowered to primitives in Python and never reach Kotlin), with the device-only
  placeholders (`CameraPreview`/`QrScanner`/`MapView`) and the documented Qt↔Compose
  divergences flagged. README links the matrix from the coverage paragraph.

## [0.11.1] — 2026-06-08

### Documentation

- **Component screenshots in the tutorials.** Added `tools/shoot_docs.py` (and a
  `make docs-shots` target) that renders every widget/component in the offscreen
  Qt simulator to `docs/assets/components/*.png` (109 images), and embedded each
  one next to its code block across the widget tutorial pages (PT + EN) — so each
  component shows its code **and** a preview. Images are the Qt-simulator render.

## [0.11.0] — 2026-06-08

### Added

- **Brazilian form components + media pickers** (`tempestroid.components`):
  `EmailInput`, `PasswordInput`, `PhoneInput`, `CPFInput`, `CNPJInput`,
  `AddressInput`, plus `ImagePicker`, `DocumentPicker` and `ImagePicture` (a
  circular profile photo). They lower to existing primitives via
  `Component.render`, so both renderers handle them with no renderer change.
- **`tempestroid.validators`** — `validate_cpf` / `validate_cnpj` (real mod-11
  check digits, reject all-same), `validate_email`, `validate_phone` (BR
  10/11 digits), shaped as `Form` validators (`Callable[[Any], str | None]`).
- **Quality-gate CLI** (mirrors tempest-fastapi-sdk): `tempest lint` / `fix`
  (`ruff check --fix` + `ruff format`, `--unsafe`) / `format` / `fmt-check` /
  `type` (pyright) / `test` (pytest) / `check` (the full gate). Each tool is
  resolved on `PATH` or via `uv run`.
- **Custom icons:** `svg_to_path(source)` converts an SVG (file or markup) into
  one normalized path `d`; `register_icon(name, source=… | path=…)` registers a
  custom icon so `Icon(name=…)` / input icon slots / `icon_path` resolve it.

### Changed

- Input icon slots (`Input` / `Autocomplete` / `Dropdown`
  `leading_icon`/`trailing_icon`) are now typed **`Icons | str | None`** — an
  `Icons` member for autocomplete over the curated set, or any string for a
  custom/platform icon.

## [0.10.0] — 2026-06-07

### Added

- **Curated icon set (`tempestroid.icons`).** A DIY, dependency-free set of 28
  common line icons (Lucide-style), each a normalized 24×24 SVG path. Public:
  `Icons` (StrEnum), `ICON_PATHS`, `icon_path(name)`, `icon_names()`. Both
  renderers draw the same stroked vector glyph; `Icon(name=…)` now renders a real
  vector instead of the bare name. **Device-verified.**
- **Input icons.** `Input` / `Autocomplete` / `Dropdown` gain
  `leading_icon` / `trailing_icon` — an icon shown inside the field on the
  start/end edge. **Device-verified.**
- **Modern secure reveal.** A `secure` `Input` now shows a modern eye / eye-off
  reveal toggle (the curated icons, not an emoji); Compose grew the toggle it
  was missing. A `lock` leading icon composes the standard password pattern.
  **Device-verified** (bidirectional mask/reveal on a Xiaomi device).
- **`tempest dev --device <preset>`** sizes the simulator window to an Android
  device preset (e.g. `pixel-7`, `galaxy-s24`); `resolve_device(name)` resolves a
  forgiving name to a `Device`. Sizes are in dp — the same layout space Compose
  uses on the device.
- **`tempest new` ships a ruff config** (line length 79) in the scaffolded
  project, plus `ruff` in a dev group.

### Changed

- **Field-level documentation.** Every widget/component field (and the typed
  event payloads) now carries a `Field(description=…)` (423 fields), so
  `introspect()`, the API reference and IDE hover show per-field help.

### Documentation

- New **enum reference** (every enum's members + meanings) and a dedicated
  **navigation guide**; full **widget tutorials** (10 per-family pages) and a
  **simulator-fidelity** section (what the Qt sim reflects vs what only the
  device shows). The example gallery links every app to its source. Installation
  split by audience (end user vs contributor); `tempest new` taught as an
  in-place scaffold. Corrected stale "Compose renders only 5 widgets" claims and
  marked Track E done. Added a `docs-doctor` maintenance agent.

## [0.9.4] — 2026-06-06

### Documentation

- **`tempest new` taught as an in-place scaffold.** The CLI already defaulted to
  scaffolding in the current directory with the folder name as the app id; the
  help text and docs now teach that flow (you are already inside your project +
  venv) instead of the subfolder-first `tempest new MyApp && cd MyApp`.
- **Documentation-accuracy sweep + a dedicated `docs-doctor` agent.** Added a
  `.claude/agents/docs-doctor.md` auditor that grounds doc claims in the source
  (`introspect()`, `tempest --help`, examples on disk, the device renderer, the
  phase tables). Its first sweep fixed: a non-existent `Select` widget referenced
  in the gallery/README (the public widget is `Dropdown`); the `Style` fields
  table missing `flex_wrap`/`stack_align`/`position`/`font_asset`/`text_scale`
  and the `FlexWrap`/`StackAlign`/`Position` enums; the API-reference and event
  catalogs that listed only the A1 primitives (now the full Track-E widget
  families + all 31 events).

## [0.9.3] — 2026-06-06

### Documentation

- **Example gallery links to every project's source.** Each app in the gallery is
  now a link to its `app.py` on GitHub (read the code + its explanatory
  docstring), the list grew from 9 to all 22 examples + the multi-file project
  (grouped by theme), and each row's one-line explanation is sourced from the
  example's real module docstring. Fixed the stale `todo` description (it has a
  real text `Input`, not a fixed pool). PT + EN.

## [0.9.2] — 2026-06-06

### Documentation

- **Full multi-file widget tutorials (PT + EN).** The single thin widgets guide
  became a tutorial hub plus 10 per-family pages under `docs/guia/widgets/`
  (`basics` / `layout` / `inputs` / `lists` / `navigation` / `overlays` /
  `animation` / `gestures` / `media` / `components`). Each widget gets a one-line
  purpose, a complete copy-pasteable example, and a prop table generated from the
  real `introspect()` schema — so the docs reflect the actual ~100-widget surface
  instead of implying a 5-widget framework. Every code block was AST-parsed and
  every import checked against the real exports.
- **Corrected stale "Compose renders only 5 widgets" claims** across the examples
  guide, architecture page, roadmap and README: both renderers (Qt + Compose)
  support the full Track E set, pinned by conformance and device-verified. The
  only device-only widgets are `CameraPreview` / `QrScanner` / `MapView` (Qt
  placeholder). Marked Track E (E0–E9) done in the roadmap/plan (it was still
  tabled as 🔜 / "planned").

## [0.9.1] — 2026-06-06

### Documentation

- **Installation page split by audience.** `docs/instalacao.md` (+ EN) now leads
  with **End users** (`pip install` + an extras table + a JDK/SDK-only Android
  build flow) and keeps **Contributors** (`uv sync` + gates + docs) as a clearly
  separated second section, instead of opening on contributor setup. The
  README install section is now end-user-first (the PyPI/GitHub face) and links
  to the guide. Fixed the stale Android prerequisites table (it claimed NDK +
  CPython toolchain were required; `tempest build apk` needs only JDK + SDK since
  the `android-host` ships in the wheel).
- **Class docstrings list their public methods.** The user-facing API classes —
  `Color`, `Edge`, `Style`, `App`, `Form`, `NavStack`, `AnimationController`,
  `Tween`, `Theme`, `Locale` — gained a `Methods:`/`Properties:` section, so the
  method surface is visible on IDE hover and in the source, not only in the
  generated API reference.

## [0.9.0] — 2026-06-06

### Added

- **`tempest clean` — reset the build caches.** Removes the rebuildable caches
  under `~/.tempestroid` (`host-extracted` / `host-src` / `src`), fixing
  stale-cache build failures after a `pip install --upgrade`. The release
  keystore (`release.jks`) is preserved by default — losing it blocks future
  Play updates — and dropped only with `--keystore`. A cache entry that can't be
  removed yields a graceful exit 1, not a crash.
- **Grouped, flow-oriented `tempest --help`.** Commands are organised into three
  panels — **Create & develop** (`new` / `dev` / `serve`), **Ship & install**
  (`install` / `icon` / `build` / `deploy` / `run`) and **Diagnose & inspect**
  (`spec` / `doctor` / `setup` / `version` / `clean`) — plus a "Typical flow"
  block (`new → dev → serve → build apk`).

### Changed

- **`tempest doctor` separates build readiness from device readiness.** The exit
  code now reflects only the build prerequisites (JDK + android-host + SDK); a
  missing `adb`/device is reported as informational ("only for run/install"),
  since `build apk`/`prd` need no device. `doctor` also probes the **JDK** and
  accepts the **wheel-bundled `_android_host`**, so a plain `pip install`
  (no repo checkout) passes the diagnosis.

## [0.8.1] — 2026-06-05

### Added

- **`tempest build apk` / `tempest build prd` — short, config-driven, per-app
  builds.** `tempest build apk` (the default) produces a debug APK with the
  project's **own `applicationId`** (so any number of tempestroid apps install
  side by side, never overwriting), reusing the **prebuilt host natives** — it
  needs only a **JDK + the Android SDK** (no NDK, no CPython toolchain; the heavy
  toolchain staging that broke from-source builds on a PyPI install is gone).
  Identity + branding are read from **`[tool.tempest]`** in pyproject.toml
  (`id` / `name` / `icon` / `splash` / `splash_bg` / `version`), so the command
  stays short — no flag soup; flags still override. `tempest build prd` is the
  store-ready release AAB. Advanced flags: `--fast` (repackage, no SDK, shared
  id), `--from-source` (stage the CPython toolchain). Gradle `build.gradle.kts`
  gained a `-Ptempest.prebuiltHost` mode that reuses the prebuilt APK's
  `libpython`/`libtempest_host`/stdlib (no CMake/NDK), so AGP still stamps the
  per-app id + all provider authorities correctly (no install collisions).
  The `android-host` Gradle project now **ships inside the wheel**
  (`tempestroid/_android_host`, ~1.3 MB of Gradle/Kotlin/C source), copied to a
  cache on first build — so `tempest build apk` works from a plain `pip install`
  with **no `git clone`** and always matched to the installed version. Verified
  end to end from a clean wheel install: `tempest new` → `tempest build apk`
  produced a per-app APK (`com.example.euapp`) via Gradle in ~23 s, no toolchain.

### Changed

- **`tempest build` / `tempest run` auto-fall back to the toolchain-free
  repackage when Gradle is unavailable.** The Gradle path needs the full
  SDK/NDK + the CPython-Android toolchain (heavy, and often unstaged on a PyPI
  install). Instead of failing, the default build now catches a Gradle/prep
  failure and falls back to repackaging the prebuilt host (the `--fast` path) so
  it still produces a shippable APK — with a clear warning that the APK keeps the
  shared `org.tempestroid.host` id (a per-app id needs the toolchain). A genuinely
  missing app file still errors. `--release` (AAB) and `--fast` are unchanged.

### Fixed

- **`tempest build` / `tempest run` (Gradle) no longer fail "SDK location not
  found" when the shell has a stale `ANDROID_HOME`/`ANDROID_SDK_ROOT`.** The
  Gradle prep used `setdefault`, which left a stale value (e.g. a non-existent
  `~/Android/Sdk`) in place; AGP reads `ANDROID_HOME` and failed. It now resolves
  a usable SDK (valid env → system fallback → managed) and **overwrites** both
  `ANDROID_HOME` and `ANDROID_SDK_ROOT`, matching the `--fast`/`deploy` paths.
  `tempest build --fast` (no Gradle) was unaffected.

## [0.8.0] — 2026-06-05

### Added

- **App icon + boot splash branding for `tempest build`.** Every APK now ships a
  default tempestroid launcher icon and an asset-drawn boot splash that covers
  the CPython start (no more blank window). Customise per app: `--icon icon.png`
  (launcher icon — Gradle build only, since the icon is a compiled resource;
  `--fast` keeps the default and warns), `--splash splash.png` and
  `--splash-bg #rrggbb` (the splash image + background — drawn by the host from
  `assets/tempest/`, so they apply on **every** build path including `--fast`).
  The splash stays up until the app's first `mount`. Device-verified on both the
  Gradle path (custom icon + splash) and `--fast` (custom splash).
- **`tempest icon <source>`** — generate a square launcher `icon.png` + a centered
  `splash.png` from one source image (Pillow), ready for `tempest build
  --icon/--splash`. Pillow is an optional extra (`pip install tempestroid[icons]`),
  imported lazily with an actionable error when absent.
- **`examples/native_caps`** — a native-capabilities gallery exercising the
  no-extra-config group on a device: `clipboard` (`set_text`/`get_text`),
  `storage` (`write_file`/`read_file`/`list_files`), `database` (SQLite
  `execute`), `secure_storage` (`set_secret`/`get_secret`) and `system`
  (`set_status_bar`/`keep_awake`). Each call returns a typed result (or a guarded
  `(device only)` / `NativeError`). Device-verified (Trilho F / F2): all five
  round-trip on a real device with their typed results.

## [0.7.0] — 2026-06-05

### Added

- **`tempest build` per-app `applicationId` (install side by side).** The default
  `tempest build` now produces the APK via Gradle `assembleDebug`, stamping each
  app with its own `applicationId` (`--app-id`, else derived `com.example.<proj>`)
  and launcher label (`--app-name`, else derived), so two tempestroid apps
  install **side by side** instead of overwriting each other (an APK repackage
  can't rewrite the binary manifest's package; Gradle can). The CLI prepares
  whatever is missing (SDK/NDK, source checkout, CPython toolchain). Verified on
  device: `com.example.appone` + `com.example.apptwo` coexist and run
  independently.
- **`tempest build --fast`.** Escape hatch that skips Gradle and repackages the
  prebuilt host (SDK build-tools only — no NDK/source/toolchain), for fast
  single-app iteration from a PyPI install. Keeps the shared
  `org.tempestroid.host` id (single app; not for side-by-side shipping).
- **`tempest new --template`/`-t`.** Scaffold a multi-file project, not just a
  single `app.py`. `multi` writes a pythonic layout (a typed `state.py`, one
  `view` per screen under `screens/`, a reusable `Card` `Component` under
  `components/`, and an `app.py` routing with `Navigator`/`Route`); `native` adds
  a screen calling native capabilities (`notify` fire-and-forget +
  `await get_position()` guarded by `on_device()`/`NativeError`). Every generated
  module stays renderer-agnostic (Qt imported lazily), so the project runs in the
  Qt simulator and on the device unchanged. `default` (single file) is unchanged.

### Fixed

- **Apps no longer white-screen on the device.** App files that imported the Qt
  renderer at module top crashed the on-device load (no PySide6) → blank window
  (APK) and a silent re-fetch storm (`tempest serve`). The counter example + the
  README quick-start now import `run_qt` lazily inside `__main__`. As a safety
  net, both device entry points and the code-push client now mount a visible
  **error screen** with the traceback (`bridge/errors.py`) instead of a blank
  window, and the dev server swallows dropped-connection errors. Verified on
  device, including live recovery on the next save.

## [0.6.2] — 2026-06-04

### Added

- **`tempest build --release` → store-ready signed AAB.** Builds the Play Store
  format (Android App Bundle) via Gradle `bundleRelease`, stamped with
  `--app-id` / `--app-version` / `--version-code` / `--keystore`. The CLI
  **auto-prepares whatever is missing**: SDK + NDK, a source checkout (cloned at
  the version tag when absent), the CPython toolchain, and a release keystore
  (generated when not supplied — back it up). The Java/JNI package stays
  `org.tempestroid.host`, so a custom `applicationId` doesn't break the bridge.
  Verified producing a valid jar-signed AAB. The default (no `--release`) stays
  the fast debug-APK repackage.

## [0.6.1] — 2026-06-04

### Changed

- **`tempest build` works from a PyPI install — no Gradle.** It now produces the
  shippable APK by **repackaging the prebuilt host**: bundle the project, inject
  it into the host APK, then re-align + re-sign via the Android SDK's
  `zipalign`/`apksigner`. No Gradle, NDK, or `android-host` checkout — just the
  SDK build-tools (`tempest setup --install` provides them). Output:
  `dist/<project>.apk` (`-o` to choose); debug-signed; runs the app standalone.
  `tempest run` = that build + install + launch + logcat. Verified on device.

### Fixed

- The host APK ships as a GitHub release asset (it embeds CPython, ~100 MB —
  past PyPI's per-file limit), downloaded by `tempest install`/`deploy`/`build`
  and cached; the wheel stays lean.

## [0.6.0] — 2026-06-04

**Build, deploy & ship — multi-file projects on a device.** Apps are now
multi-file: the whole importable project tree (root = nearest `pyproject.toml`)
is bundled onto `sys.path` in the simulator and on the device, so
`from my_pkg import x` resolves identically everywhere.

### Added

- **`tempest build`** now produces a **standalone, shippable APK** with the
  project baked in (runs with no dev server); **`tempest deploy`** is the new
  offline, no-toolchain device push (install bundled host + push project +
  launch); **`tempest setup`** configures the Android build environment
  (diagnose JDK/SDK/NDK/build-tools; `--install` installs the SDK + NDK).
- **Multi-file project bundle** (`tempestroid.cli.bundle`): `resolve_project`,
  `build_bundle`, `extract_bundle`, `tree_signature`; `spec_from_project` loader;
  `run_device_bundle` device entry; Kotlin host extracts the bundle onto
  `sys.path`.
- **Background tasks re-enter Python** (`on_background_task`): the WorkManager
  worker dispatches a fired task into the live interpreter, or boots a fresh
  short-lived one when the process was woken from dead. One-shot
  (`interval_s=None`) or periodic scheduling.
- **Accessibility** labels now cross the bridge — `Semantics` is lowered to the
  device a11y tree (TalkBack-readable).
- **Optional FCM**: the google-services Gradle plugin is applied only when an
  `android-host/app/google-services.json` is present, so the host still builds
  without a Firebase project.

### Fixed

- **Biometrics** reach the system service: the host `MainActivity` is now a
  `FragmentActivity` (required by `BiometricPrompt`).
- The published wheel bundles the prebuilt host APK (publish CI fetches it from
  the release), so `tempest install` / `deploy` work fully offline.

### Verified on device (Xiaomi 23053RN02A)

- Shippable multi-file APK (cold launch, interactive); E9 dark mode / i18n / RTL;
  E8 haptics, lifecycle, prefs, sensors, WorkManager re-entering Python (→
  notification), biometrics path, local + FCM-token push paths, semantics.

## [0.5.0] — 2026-06-04

**Trilho E — Flutter/React Native parity (E0–E9).** Ten phases land the
cross-platform surface that closes the gap with Flutter + React Native. Every
phase ships the three matched layers (renderer-agnostic IR/diff + Qt translator
+ Compose translator) with both renderers green; the device half (Compose on a
physical arm64 device) is verified where hardware allows. ~160 new public
exports — see the README for the full API.

### Added

- **Navigation & routes (E0).** `Navigator` / `NavStack` / `Route` push-pop
  stack, `TabView` / `TabBar` tabs, `RouteDrawer` slide-over drawer, Android
  back button (`BACK_TOKEN` → `App.pop`) and deep-link parsing
  (`routes_from_path`, `DeepLinkEvent`). Typed `RouteChangeEvent`; per-route
  slide/fade transitions in both renderers.
- **Virtualized lists & scroll (E1).** `LazyColumn` / `LazyRow` / `LazyGrid`
  materialize only the visible window into keyed children; `SectionList` /
  `SectionHeader` with sticky headers; `RefreshControl` pull-to-refresh
  (`RefreshEvent`); infinite scroll via `ScrollEvent` + `EndReachedEvent`
  (`App.slide_window`). 10k-item lists scroll fluidly on both renderers.
- **Overlays & feedback (E2).** `Dialog`, `BottomSheet`, `Toast`, `Tooltip`,
  `Menu` / `Popover` / `ActionSheet` (with `MenuItem` / `MenuSelectEvent`),
  driven by a z-ordered overlay layer (`Scene` / `OverlayEntry` /
  `build_scene` / `diff_scene`); barrier scrim, anchored menus, auto-expiring
  toasts, `DISMISS_TOKEN_PREFIX` for host-initiated dismissal.
- **Animation framework (E3).** `AnimationController` / `Tween` / `Spring` with
  a deterministic clock that crosses the bridge via `FRAME_TOKEN`
  (`App._tick_from_device`); `Animated`, `AnimatedList`, `Hero` shared-element
  transitions, `Shimmer` / `Skeleton`. `has_animations` on the mount/patch
  envelope gates `withFrameNanos` on the host.
- **Advanced gestures (E4).** `Draggable` / `DragTarget` (`DragEvent`),
  `InteractiveViewer` pinch-zoom (`ScaleEvent` / `PanEvent`), double-tap,
  `Dismissible` swipe-to-delete (`DismissEvent`), `ReorderableList`
  (`ReorderEvent`). Each gesture emits a typed event and drives state.
- **Inputs & forms (E5).** `Dropdown` (`SelectEvent`), `TimePicker`
  (`TimeChangeEvent`), `RangeSlider` (`RangeChangeEvent`), `Autocomplete`,
  `PinInput` (`SubmitEvent`), `MaskedInput`; `Form` / `FormField` / `FormState`
  with `Validator` / `ValidationEvent` — validation runs in Python and blocks
  invalid submit with per-field errors on both renderers.
- **Refined layout (E6).** `Wrap` / `FlexWrap` flow wrapping, `PageView`
  pager/carousel (`PageChangeEvent`), `CollapsingAppBar` (sliver-style collapse
  on scroll), `Table` / `TableRow` / `TableCell` / `DataTable`, `AspectRatio`.
- **Media & graphics (E7).** `Canvas` with a JSON draw-command list
  (`DrawCommand` / `MoveTo` / `LineTo` / `ArcTo` / `DrawRect` / `DrawOval` /
  `DrawText` / `FillCmd` / `StrokeCmd`), `Svg`, `VideoPlayer`, `WebView`,
  `Blur` / `BackdropFilter`, `ClipShape` / `ClipPath`, `CameraPreview`,
  `QrScanner` (`QrScanEvent`), `MapView`.
- **Platform & system (E8).** Haptics (`vibrate` / `impact` / `ImpactStyle`),
  sensors (`start_sensor` / `stop_sensor` / `SensorEvent` / `SensorType` /
  `SensorCallback`, `SENSOR_TOKEN_PREFIX`), app lifecycle (`on_app_state_change`
  / `AppState` / `LifecycleEvent`, `LIFECYCLE_TOKEN`), permissions
  (`request_permission` / `check_permission` / `PermissionStatus` /
  `PermissionResult`), biometrics (`authenticate` / `BiometricResult`), secure
  storage (`set_secret` / `get_secret` / `delete_secret`), preferences
  (`set_pref` / `get_pref` / `delete_pref` / `get_all_prefs`), SQLite (`execute`
  / `execute_many` / `QueryResult`), connectivity (`get_connectivity` /
  `on_connectivity_change` / `ConnectivityState` / `ConnectivityEvent`,
  `CONNECTIVITY_TOKEN_PREFIX`), push (`register_push` / `PushToken` /
  `schedule_notification`), background tasks (`schedule_task` / `cancel_task`),
  system controls (`set_status_bar` / `StatusBarStyle` / `get_brightness` /
  `set_brightness` / `keep_awake` / `set_orientation` / `Orientation`),
  `KeyboardAvoidingView`, and `NativeError`. Verified on device: haptics,
  lifecycle, preferences, `KeyboardAvoidingView`.
- **Cross-cutting (E9).** Theming (`Theme` / `ThemeMode` / `App.set_theme`,
  `ThemeChangeEvent` over `THEME_TOKEN`) with light/dark; `MediaQueryData` /
  `Orientation`; i18n/RTL (`Locale` / `translate` / `t` / `App.set_locale`,
  `LocaleChangeEvent` over `LOCALE_TOKEN`) — RTL mirrors start/end edges and
  text-align in both translators; accessibility (`Semantics` + `focusable` /
  `focus_order` on the `Widget` base); custom fonts + scale (`Style.text_scale`
  / `font_asset`). Verified on device: dark mode, RTL + Arabic i18n.

### Fixed

- Apply `SafeArea` (system-bars insets) to the Compose root by default.
- Compose `Button` honors `Style.background` / `color` via
  `ButtonDefaults.buttonColors` instead of letting the Material default (purple)
  paint over it; single-glyph operator keys no longer collapse.
- Defer the `run_qt` import in `examples/theming/app.py` into `main()` so the
  device code-push path (no PySide6) can re-exec the app.

## [0.4.0] — 2026-05-31

### Added

- **Compose device cases for the utility widgets.** The Compose renderer now
  draws **`Switch`**, **`Slider`**, **`ProgressBar`**, **`Spinner`**,
  **`TextArea`**, **`ScrollView`**, **`Image`** (via Coil) and **`Icon`** (named
  Material icons) on the device, instead of falling back to an empty `Box`. Adds
  the `material-icons-extended` + `coil-compose` host dependencies. (`Stack` /
  `GestureDetector` already rendered, shipped with the overlay.)
- **Camera parameters (photo + video).** `take_photo(camera, max_width,
  max_height)` takes a facing + size caps; new `record_video(camera,
  max_duration_s, quality) -> Video`. The Kotlin camera handler builds the
  `ACTION_IMAGE_CAPTURE` / `ACTION_VIDEO_CAPTURE` intent with the requested
  extras, downscales photos to the caps, and reads video metadata.
- **Microphone + speaker capabilities (`tempestroid.native.audio`).**
  `record_audio() -> AudioClip` (microphone, `MediaRecorder`) and
  `play_sound(src, volume)` / `stop_sound()` (speaker, `MediaPlayer`) over the
  existing request/response native channel. `RECORD_AUDIO` added to the manifest.

### Changed

- **Keyed mixed diff in one pass.** When both child lists are fully keyed with
  unique keys, the reconciler now handles insert + remove + reorder together in a
  single pass (a pure permutation is the no-add/remove case), instead of the
  positional fallback.

### Fixed

- **On-device code-push no longer needs Typer.** The CLI's Typer import is
  deferred so the device-side code-push re-exec path runs without the `typer`
  dependency present.
- **Photo dimensions come from the camera capability.** `take_photo` now reports
  the real captured width/height instead of a placeholder.

## [0.3.0] — 2026-05-31

### Added

- **Overlay + gestures.** New **`Stack`** widget (z-order overlay; children share
  one box, `position=ABSOLUTE` anchors by `top`/`right`/`bottom`/`left` insets,
  others align by **`StackAlign`**) and **`GestureDetector`** (wraps a child,
  reports gestures via **`TapHandler`** / **`LongPressHandler`** / **`SwipeHandler`**:
  `on_tap` / `on_double_tap` / `on_long_press` / `on_swipe`). Adds the
  **`LongPressEvent`** / **`SwipeEvent`** (+ **`SwipeDirection`**) typed events and
  the **`Position`** style enum. Realized in the Qt renderer; the Compose device
  cases ship next.
- **Device screen-size presets (`tempestroid.devices`).** **`Device`** — an enum
  of logical (dp) viewport sizes for common phones (Pixel, Galaxy, Redmi, Poco,
  …) with `.size`; **`DEFAULT_DEVICE`** sizes the simulator window so it matches a
  real device instead of a generic guess.
- **`tempest install` — install the prebuilt host on a device (no SDK/NDK).**
  Resolves the host APK from an explicit `.apk`/URL → `TEMPESTROID_HOST_APK` → a
  bundled asset (in source checkouts) → a download from the matching GitHub
  release (`TEMPESTROID_HOST_APK_URL` override), cached under `~/.cache/tempestroid`.
  After installing once, `tempest serve` pushes app code over LAN.
- **`tempest new .` scaffolds in place, fully configured.** Writes `app.py`,
  `pyproject.toml` (with the `tempestroid[qt]` dependency and a `[tool.tempest] app`
  pointer), `README.md` and `.gitignore`. `.` (the default) targets the current
  directory; a name creates a subdirectory.
- **No-argument app commands.** `tempest dev` / `serve` / `build` / `run` read the
  app path from `[tool.tempest] app` in the nearest `pyproject.toml` when no path
  is passed, so inside a project the commands take no arguments.
- **`tempest serve` closes the device loop.** With a device connected it now
  auto-wires `adb reverse` and launches the host in dev mode pointed at the dev
  server (`--no-launch` to serve only).

### Changed

- **CLI migrated to Typer** — global `--version`/`-V` flag plus a `version`
  command, `no_args_is_help`, richer help.
- **`tempest build` fails with an actionable hint from an installed wheel** —
  when the `android-host` source tree is absent, the error points at the
  `tempest install` + `tempest serve` device path.

## [0.2.0] — 2026-05-31

### Added

- **Composite component set expanded.** App shell primitives now include
  `AppBar`, `Scaffold`, `NavBar`, `Sidebar`, `Footer`, `Header`, `SafeArea`,
  `Menu`, `Drawer`, `Calendar`, `Clock`, `Card`, `Selection`, `Field`,
  `Feedback`, `Disclosure`, and navigation-focused widgets.
- **Native capability layer.** The Python↔Kotlin bridge now covers
  geolocation, sharing, camera, file storage, clipboard, Bluetooth scan, and
  the request/response native envelope.
- **CLI and device workflow polish.** `tempest build` / `tempest run` became
  more transparent, and the repository now includes a dedicated WSL device-run
  guide for USB/IP + `adb` mirroring.
- **Example and docs refresh.** The gallery and supporting docs were updated
  alongside the new component and device flows.

## [0.1.0] — 2026-05-31

First public release. The framework (Trilho A) is complete and the Android
runtime (Trilho B, phases B0–B6) is validated on a real arm64 device.

### Added

- **Typed declarative UI core.** A frozen-Pydantic `Style` model (`Color`,
  `Edge`, `Border`, `Transition`, and the style enums) and a widget IR
  (`Widget`, `Text`, `Button`, `Column`, `Row`, `Container`, plus value-bearing
  inputs and utility widgets).
- **Renderer-agnostic reconciler** — `build → diff → patch` (`Insert` / `Remove`
  / `Update` / `Reorder` / `Replace`).
- **Qt desktop simulator** (`run_qt`, optional `qt` extra) with a `Style → Qt`
  translator and an asyncio×Qt event loop via `qasync`.
- **Async-first state runtime** (`App`) with coalesced rebuilds and **stateful
  hot reload** (`App.swap_view`).
- **`tempest` CLI** — `dev` (simulator + hot reload/restart cockpit), `serve`
  (LAN code-push to a device), `spec` (typed contract as JSON), `new` (scaffold
  a project), `build` (bundle an app into an APK), `run` (build + install +
  logcat).
- **Android runtime (Trilho B).** Official CPython 3.14 (PEP 738) embedded via a
  hand-rolled JNI bridge in a Kotlin/Gradle host; native wheels (`pydantic-core`)
  via cibuildwheel; a Jetpack Compose renderer; a LAN dev server with QR pairing;
  and native capabilities (notifications).
- **Conformance suite** pinning the Qt and Compose `Style` translators with
  golden snapshots (phase D).

[Unreleased]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.8.1...HEAD
[0.8.1]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.6.2...v0.7.0
[0.2.0]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mauriciobenjamin700/tempestroid/releases/tag/v0.1.0
