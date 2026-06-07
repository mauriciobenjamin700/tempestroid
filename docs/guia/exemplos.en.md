# Example gallery

A set of runnable example apps lives in
[`examples/`](https://github.com/mauriciobenjamin700/tempestroid/tree/main/examples).
Each exposes the same `make_state()` + `view(app)` contract, so it runs in the Qt
simulator **and** on the device via code-push, with no changes. **Click any app
name below to read the source** — every `app.py` opens with a docstring
explaining what it demonstrates.

```bash
# Qt simulator on desktop (needs the `qt` extra; installed by `uv sync`)
uv run python examples/<name>/app.py
uv run tempest dev examples/<name>/app.py     # + hot reload on save

# On an Android device, via LAN code-push (phase B5)
adb reverse tcp:8765 tcp:8765                 # over USB; skip on the same Wi-Fi
uv run tempest serve examples/<name>/app.py
```

## Fundamentals

| App | What it shows | Exercises |
|---|---|---|
| [`counter`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/counter/app.py) | The basics: sync **and** `async` handlers mutate state and trigger a coalesced rebuild. | `Text`, `Button`, `Row`/`Column`; `update`. |
| [`stopwatch`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/stopwatch/app.py) | Async-first loop: a coroutine handler ticks via `asyncio.sleep` without freezing the UI (stop/reset stay tappable). | Coalesced rebuilds driven off the loop; `update`. |
| [`todo`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/todo/app.py) | Type a task into the `Input` and tap "add"; tapping toggles done; "clear done" removes finished ones. | `Input` + stable key; **every** child patch: `insert` / `remove` / `update`. |
| [`calculator`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/calculator/app.py) | The button grid **is** the input (no text widget) — a dense-layout showcase. | Nested `Row`/`Column`, keyed buttons; `update` on the display. |
| [`colorpicker`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/colorpicker/app.py) | Dynamic `Style`: swatches re-color a live preview; toggles re-style its text. | `background` / `font_size` / `font_weight` through the diff. |

## Components & shell

| App | What it shows | Exercises |
|---|---|---|
| [`shell`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/shell/app.py) | A full screen built from the composite components: `Scaffold` + `AppBar` (with `Burger`/`Drawer`) on top, `NavBar` at the bottom. | `tempestroid.components` lowered to primitives via `Component.render`. |
| [`gallery`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/gallery/app.py) | Utility widgets + input styling + an implicit `Style` transition. | `Slider`/`Switch`/`ProgressBar`/`Spinner`/`Image`/`Icon`/`ScrollView`/`TextArea`; secure + regex `Input`; `Style.transition`. |

## Track E — Flutter/RN parity

| App | What it shows | Exercises |
|---|---|---|
| [`navigation`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/navigation/app.py) | The three navigation hosts: animated push/pop stack, tabs and drawer. | `Navigator` / `TabView` / `RouteDrawer` (E0). |
| [`tabs`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/tabs/app.py) | A persistent tab bar swaps the body across 3 panels; shared state survives the switch. | The canonical tabbed-navigation pattern. |
| [`lists`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/lists/app.py) | A 10k-item `LazyColumn` + pagination + pull-to-refresh, and a `SectionList` with sticky headers. | Windowed virtualization (E1). |
| [`overlays`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/overlays/app.py) | Dialog, bottom sheet, menu and toast through the `App` imperative overlay API. | The z-ordered overlay layer (E2). |
| [`animation`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/animation/app.py) | A box easing color/opacity, an animated list, `Hero` and `Shimmer`. | `AnimationController` + `Tween` on the frame clock (E3). |
| [`gestures`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/gestures/app.py) | Swipe-to-delete (`Dismissible`), drag-to-reorder and pinch-to-zoom. | Advanced gestures (E4). |
| [`forms`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/forms/app.py) | A `Form` of `FormField`s with typed validators (blocks invalid submit) + selection/segmented inputs. | Python-side validation before patches (E5). |
| [`form`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/form/app.py) | The basic value-bearing inputs, each folding its typed event back into state. | `Input` / `Checkbox` / `DatePicker` / `FilePicker` + typed events. |
| [`layout`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/layout/app.py) | `Wrap` chips, a paginated `PageView` and a `CollapsingAppBar` that shrinks on scroll. | Refined layout (E6). |
| [`media`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/media/app.py) | `Canvas` drawing, `Svg`, blur and clip. | Media & graphics (E7). |
| [`platform`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/platform/app.py) | Haptics, real preferences, the lifecycle stream and `KeyboardAvoidingView`. | Platform/system (E8) — runs on Qt and on device. |
| [`theming`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/theming/app.py) | A dark/light toggle (`App.set_theme`), a PT↔Arabic/RTL locale (`App.set_locale`) and `Semantics`. | Cross-cutting: theme/i18n/accessibility (E9). |

## Device & multi-file

| App | What it shows | Exercises |
|---|---|---|
| [`device_counter`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/device_counter/app.py) | A minimal counter with **no Qt import** — the code-push target on the device. | Same contract, Qt-free (B5). |
| [`native_caps`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/native_caps/app.py) | Native capabilities needing no extra config, each a typed request/response round-trip. | `clipboard` / `storage` / `database` (SQLite) / `secure_storage` / `system` (device-verified). |
| [`sysverify`](https://github.com/mauriciobenjamin700/tempestroid/blob/main/examples/sysverify/app.py) | An on-device verification harness for the capabilities that need real hardware. | Sensors / biometrics / push (device-only). |
| [`multifile`](https://github.com/mauriciobenjamin700/tempestroid/tree/main/examples/multifile) | A **multi-file** project (`main.py` + a `widgets/` package) — what `tempest new --template multi` generates. | Whole-project bundle on `sys.path` (Track C). |

## Current widget set

**Both renderers** — the Qt simulator (desktop) and Compose (device) — support
the full Track E set. The old "Compose only renders five widgets" gap is gone:
the value-bearing inputs (`Input` / `TextArea` / `Checkbox` / `Switch` /
`Slider` / `Select` / `DatePicker` / `FilePicker` / …) render **natively on the
device** via Jetpack Compose and fold their typed events back into state. Parity
is pinned by the conformance suite (golden snapshots of both `Style → Qt` and
`Style → Compose` translators) and was verified on a device across E0–E9.

Coverage (both renderers, unless noted):

| Category | Widgets |
|---|---|
| Layout | `Column` / `Row` / `Container` / `Stack` / `Wrap` / `ScrollView` / `SafeArea` / `AspectRatio` / `PageView` / `KeyboardAvoidingView` |
| Text & action | `Text` / `Button` / `Icon` / `Image` (`on_click`) |
| Value inputs | `Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider` / `Select` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` / `MaskedInput` / `Autocomplete` / `Form` / `FormField` |
| Virtualized lists | `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` (+ pull-to-refresh, infinite scroll) |
| Navigation | `Navigator` / `TabView` / `TabBar` / `RouteDrawer` |
| Overlays | `Dialog` / `BottomSheet` / `Menu` / `Popover` / `Toast` / `Tooltip` / `ActionSheet` |
| Animation | `Animated` / `AnimatedList` / `Hero` / `Shimmer` / `Skeleton` |
| Gestures | `GestureDetector` / `PanHandler` / `ScaleHandler` / `DoubleTapHandler` / `Draggable` / `DragTarget` / `Dismissible` / `ReorderableList` / `InteractiveViewer` |
| Media & graphics | `Canvas` / `Svg` / `VideoPlayer` / `WebView` / `Blur` / `BackdropFilter` / `ClipPath` |
| Indicators | `ProgressBar` / `Spinner` |

!!! note "Media/camera divergence (device-only)"
    A few hardware widgets — `CameraPreview` / `QrScanner` / `MapView` — render
    only on the device (Compose) and show up as a **signalled placeholder on
    Qt**, not the other way around. Per-field divergences between the two
    translators are documented in the conformance suite (`tests/conformance/`).

The `form` and `gallery` examples exercise the real value inputs — in the
simulator **and** on the device. Apps like `calculator` stay keypad-driven by
app design, not by a renderer limit.

!!! tip "Stable handlers"
    Rebuilds compare handler props by identity, so a fresh `lambda` each build
    reads as a prop change (a known limitation). The examples still emit correct
    patches — just more than the strict minimum. Prefer stable handler references
    in production apps.
