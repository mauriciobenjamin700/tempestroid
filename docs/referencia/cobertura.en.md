# Renderer coverage (Qt vs Compose)

tempestroid has **one reconciler and two leaf renderers**: **Qt** (desktop
simulator) and **Compose** (Android device, Kotlin). This page is the matrix of
**which widget each renderer handles** — the reference for what runs on the
device beyond the simulator.

!!! info "What each column means"
    - **Qt (simulator)** — the widget has a render path in the Qt renderer
      (`tempestroid/renderers/qt/`).
    - **Compose (device)** — the Kotlin renderer
      (`android-host/.../TempestRenderer.kt`) has an **explicit case** building a
      real Composable for the node's `type` (it does not fall through to the
      `Box`/`Popup` fallback).
    - This matrix reflects **code-level coverage** (a handler exists). Per-widget
      **on-device verification** (a screenshot of each one on hardware) happens in
      the E-phase *device-verify* runs and is ongoing work — where it has not been
      exercised, it is flagged.

!!! check "Summary"
    **Every exported primitive widget has a handler in both renderers.** The
    Compose renderer has **62 primitive cases + 7 overlay cases**; any `type`
    without a case falls into a forward-compat `Box`/`Popup` (never breaks). The
    **composite components** (`tempestroid/components/`) are lowered to primitives
    in Python (`Component.render`) before serialization — so they **never reach
    Kotlin**: they render through their primitive children on both sides.

## Layout

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Column` | ✅ | ✅ | |
| `Row` | ✅ | ✅ | |
| `Container` | ✅ | ✅ | On Compose it hits the forward-compat `Box` (style + children). |
| `Stack` | ✅ | ✅ | Z-order; `position=ABSOLUTE` anchors by insets. |
| `SafeArea` | ✅ | ✅ | Compose insets against `WindowInsets.safeDrawing`. |
| `Wrap` | ✅ | ✅ | Line wrap pinned by conformance (`flex_wrap`). |
| `AspectRatio` | ✅ | ✅ | |
| `PageView` | ✅ | ✅ | Emits `PageChangeEvent`. |
| `ScrollView` | ✅ | ✅ | |
| `KeyboardAvoidingView` | ✅ | ✅ | |

## Text, action and indicators

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Text` | ✅ | ✅ | |
| `Button` | ✅ | ✅ | |
| `Icon` | ✅ | ✅ | Named Material icons. |
| `Image` | ✅ | ✅ | Compose via Coil. |
| `ProgressBar` | ✅ | ✅ | |
| `Spinner` | ✅ | ✅ | |

## Inputs and forms

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Input` | ✅ | ✅ | |
| `TextArea` | ✅ | ✅ | |
| `Checkbox` | ✅ | ✅ | |
| `Switch` | ✅ | ✅ | |
| `Slider` | ✅ | ✅ | |
| `RangeSlider` | ✅ | ✅ | Qt: two `QSlider`s; Compose: M3 `RangeSlider`. |
| `Dropdown` / `Select` | ✅ | ✅ | |
| `TimePicker` | ✅ | ✅ | Qt: inline spinner; Compose: M3 dialog. |
| `DatePicker` | ✅ | ✅ | |
| `FilePicker` | ✅ | ✅ | |
| `Autocomplete` | ✅ | ✅ | |
| `PinInput` | ✅ | ✅ | |
| `MaskedInput` | ✅ | ✅ | |
| `FormField` | ✅ | ✅ | Validation runs in Python; the renderer only draws the error. |
| `Form` | ✅ | ✅ | |

## Virtualized lists

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `LazyColumn` | ✅ | ✅ | Window materialized by the app; see [divergences](#divergences). |
| `LazyRow` | ✅ | ✅ | |
| `LazyGrid` | ✅ | ✅ | |
| `SectionList` | ✅ | ✅ | Sticky header: floating `QLabel` (Qt) vs `stickyHeader` (Compose). |
| `RefreshControl` | ✅ | ✅ | Qt: `refreshing` prop (no pull gesture); Compose: `PullToRefreshBox`. |

## Navigation

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Navigator` | ✅ | ✅ | Qt: `QStackedWidget` + `QPropertyAnimation`; Compose: `AnimatedContent`. |
| `TabView` | ✅ | ✅ | |
| `TabBar` | ✅ | ✅ | |
| `RouteDrawer` | ✅ | ✅ | Compose: `ModalDrawer`. |

## Overlays and feedback

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Dialog` | ✅ | ✅ | Compose: M3 `AlertDialog`. |
| `BottomSheet` | ✅ | ✅ | Compose: `ModalBottomSheet`. |
| `ActionSheet` | ✅ | ✅ | |
| `Toast` | ✅ | ✅ | |
| `Menu` | ✅ | ✅ | Compose: `DropdownMenu`. |
| `Popover` | ✅ | ✅ | |
| `Tooltip` | ✅ | ✅ | |

## Animation

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Animated` | ✅ | ✅ | Frame clock crosses the bridge (`FRAME_TOKEN`). |
| `AnimatedList` | ✅ | ✅ | |
| `Shimmer` | ✅ | ✅ | |
| `Skeleton` | ✅ | ✅ | |
| `Hero` | ✅ | ✅ | Shared transition across screens. |

## Gestures

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `GestureDetector` | ✅ | ✅ | `on_tap` / `on_double_tap` / `on_long_press` / `on_swipe`. |
| `PanHandler` | ✅ | ✅ | |
| `ScaleHandler` | ✅ | ✅ | Pinch/zoom. |
| `DoubleTapHandler` | ✅ | ✅ | |
| `Draggable` | ✅ | ✅ | |
| `DragTarget` | ✅ | ✅ | |
| `Dismissible` | ✅ | ✅ | Swipe-to-delete. |
| `ReorderableList` | ✅ | ✅ | |
| `InteractiveViewer` | ✅ | ✅ | |

## Media and graphics

| Widget | Qt (simulator) | Compose (device) | Notes |
|---|:---:|:---:|---|
| `Canvas` | ✅ | ✅ | Identical JSON command list (conformance). |
| `Svg` | ✅ | ✅ | |
| `Blur` / `BackdropFilter` | ✅ | ✅ | |
| `ClipPath` | ✅ | ✅ | |
| `VideoPlayer` | ✅ | ✅ | Compose via `AndroidView`. |
| `WebView` | ✅ | ✅ | Compose via `AndroidView`. |
| `CameraPreview` | ⚠️ placeholder | ✅ device | Qt shows a flagged placeholder; real camera is device-only. |
| `QrScanner` | ⚠️ placeholder | ✅ device | same — QR scanning is device-only. |
| `MapView` | ⚠️ placeholder | ✅ device | same — a real map is device-only. |

## Composite components

Everything in `tempestroid/components/` (`AppBar`, `Scaffold`, `NavBar`,
`Sidebar`, `Footer`, `Header`, `Card`, `Drawer`, `Calendar`, `Clock`, the BR
form components, etc.) is **lowered to primitives in Python** by
`Component.render` before the diff. The reconciler never serializes a `Component`
type to the device — Kotlin only sees the primitive children. So components
inherit the coverage of the primitives they emit, identical on both renderers.

## Documented divergences {#divergences}

The two renderers match in **behavior and event payload** but use different
native mechanisms. The divergences pinned by the
[conformance suite](../roadmap.md) (phase D) and described in `CLAUDE.md`:

- **Lists:** the Qt scroll area spans only the materialized window (no reserved
  virtual extent); Compose's `LazyColumn` reports `layoutInfo` against the full
  `itemCount`.
- **Overlays:** Qt uses `QDialog`/`QMenu`/`QTimer`; Compose uses Material3
  (`AlertDialog`/`ModalBottomSheet`/`DropdownMenu`), which manage their own scrim
  and `WindowInsets.safeDrawing`.
- **Navigation:** Qt animates with `QPropertyAnimation`; Compose with
  `AnimatedContent`/`ModalDrawer`. The Android *back* button is the device path
  (vs `Esc` in the simulator).
- **Device-only media:** camera, QR and map are flagged placeholders on Qt and
  real only on the device.

!!! note "Source of truth"
    The **Compose (device)** column is derived straight from the
    `when (node.type)` in `android-host/app/src/main/java/.../TempestRenderer.kt`
    (primary + overlay dispatch). When adding a new widget, ensure a case there
    **and** a row in this matrix.
