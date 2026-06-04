# Changelog

All notable changes to **tempestroid** are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mauriciobenjamin700/tempestroid/releases/tag/v0.1.0
