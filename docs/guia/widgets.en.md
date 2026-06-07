# Widgets

Widgets are the declarative IR primitives — a tree of Pydantic models the
reconciler diffs and the renderers apply. Always import from the package level:
`from tempestroid import Text, Button, ...`.

The framework exports **~100 widgets**, all supported by **both renderers** (the
Qt simulator on desktop + Compose on the device). This page is the index; each
family has its own tutorial page with complete examples and a per-widget prop
table.

## Catalog by family

| Family | Covers |
|---|---|
| [Text, action & indicators](widgets/basics.md) | `Text` / `Button` / `ProgressBar` / `Spinner` |
| [Layout](widgets/layout.md) | `Column` / `Row` / `Container` / `Stack` / `Wrap` / `ScrollView` / `SafeArea` / `AspectRatio` / `PageView` / `KeyboardAvoidingView` |
| [Value inputs](widgets/inputs.md) | `Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider` / `Dropdown` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` / `MaskedInput` / `Autocomplete` / `Form` / `FormField` |
| [Virtualized lists](widgets/lists.md) | `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` / `RefreshControl` |
| [Navigation](widgets/navigation.md) | `Navigator` / `TabView` / `TabBar` / `RouteDrawer` |
| [Overlays & feedback](widgets/overlays.md) | `Dialog` / `BottomSheet` / `Menu` / `Popover` / `Toast` / `Tooltip` / `ActionSheet` |
| [Animation](widgets/animation.md) | `Animated` / `AnimatedList` / `Hero` / `Shimmer` / `Skeleton` |
| [Gestures](widgets/gestures.md) | `GestureDetector` / `PanHandler` / `ScaleHandler` / `DoubleTapHandler` / `Draggable` / `DragTarget` / `Dismissible` / `ReorderableList` / `InteractiveViewer` |
| [Media & graphics](widgets/media.md) | `Image` / `Icon` / `Canvas` / `Svg` / `VideoPlayer` / `WebView` / `Blur` / `BackdropFilter` / `ClipPath` / `CameraPreview` / `QrScanner` / `MapView` |
| [Composite components](widgets/components.md) | `Card` / `ListTile` / `Scaffold` / `AppBar` / `NavBar` / `SegmentedControl` / `Rating` / `Table` … (29) |

!!! tip "Where to start"
    New here? Follow this order: **[Text, action &
    indicators](widgets/basics.md)** → **[Layout](widgets/layout.md)** →
    **[Value inputs](widgets/inputs.md)**. Read the rest on demand.

## Cross-cutting concepts

These hold for any widget — worth reading before diving into the families.

### Keys (`key`)

Give every child of a list a stable `key`. The reconciler uses keys to emit a
`Reorder` instead of recreating widgets, and to match nodes across rebuilds.

### Traversing the tree

Every widget exposes `child_nodes()` — use it to walk the tree generically,
without reaching into each type's internal storage. Leaves (`Text`, `Image`,
inputs) return `[]`.

### Style, semantics & focus

Every `Widget` subclass accepts `style` (a [`Style`](estilos.md)),
`semantics`/`focusable`/`focus_order` (accessibility) and `key`. That's why those
props don't appear in each family's tables — they are universal.

### Per-widget event contract

Each widget declares the event every handler emits via the `event_schemas`
classvar (e.g. `Button.event_schemas == {"on_click": TapEvent}`). That contract
is published by [`introspect()`](../referencia/api.md) and consumed by the device
boundary. See [Events](eventos.md).

!!! info "Both renderers reach parity"
    The full set renders in both the **Qt simulator** and on the **device
    (Compose)** — parity is pinned by the conformance suite (golden snapshots of
    both `Style` translators). The only exception is a few hardware widgets
    (`CameraPreview` / `QrScanner` / `MapView`), which are **device-only** and
    show a signalled placeholder on Qt.

## Recap

- Widgets are Pydantic models; always import from the package level
  (`from tempestroid import ...`).
- ~100 widgets across 10 families — use the catalog above.
- Value inputs emit a typed change event (`on_change` / `on_select`); give list
  children a stable `key`.
- `style`/`semantics`/`focusable`/`key` are universal to every widget.

## Next steps

➡️ Make widgets pretty with **[Styles](estilos.md)**, learn the typed
**[Events](eventos.md)**, or see full apps in the **[Examples
gallery](exemplos.md)**.
