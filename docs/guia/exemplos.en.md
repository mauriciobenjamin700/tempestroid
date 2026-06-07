# Example gallery

A set of runnable example apps lives in `examples/`. Each exposes the same
`make_state()` + `view(app)` contract, so it runs in the Qt simulator **and** on
the device via code-push, with no changes.

```bash
# Qt simulator on desktop (needs the `qt` extra; installed by `uv sync`)
uv run python examples/<name>/app.py
uv run tempest dev examples/<name>/app.py     # + hot reload on save

# On an Android device, via LAN code-push (phase B5)
adb reverse tcp:8765 tcp:8765                 # over USB; skip on the same Wi-Fi
uv run tempest serve examples/<name>/app.py
```

## Apps

| App | What it shows | Widgets / patches exercised |
|---|---|---|
| `counter` | The basics: sync **and** `async` handlers. | `Text`, `Button`, `Row`/`Column`; `update`. |
| `shell` | The composite components: a `Scaffold` with an `AppBar` on top and a `NavBar` at the bottom, body per tab. | `tempestroid.components` (`AppBar`/`Scaffold`/`NavBar`/`Header`) lowered to primitives via `Component.render`. |
| `todo` | Tap-driven list (no text input — items come from a fixed pool). | Stable-key list; `insert` / `remove` / `update`. |
| `calculator` | Dense button grid as the only input. | Nested `Row`/`Column`, 16 keyed buttons; `update` on the display. |
| `stopwatch` | Async-first loop: a coroutine handler ticks via `asyncio.sleep` without freezing the UI. | Coalesced rebuilds driven off the loop; `update`. |
| `colorpicker` | Dynamic `Style`: swatches re-color a live preview; toggles re-style its text. | `background` / `font_size` / `font_weight` updates through the diff. |
| `form` | The value-bearing inputs, each folding its typed event back into state. | `Input` / `Checkbox` / `DatePicker` / `FilePicker`; `TextChangeEvent` / `ToggleEvent` / `DateChangeEvent` / `FileSelectEvent`. |
| `gallery` | The expanded component set + input styling + an implicit `Style` transition. | `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`; secure + regex `Input`; `SlideEvent`; `Style.transition`. |
| `device_counter` | Minimal device-only counter (no Qt import) for the code-push path. | Same contract, Qt-free. |

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
