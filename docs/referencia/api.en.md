# Public API

Everything below is importable from the top-level `tempestroid` package. Always
import from the package level, never from submodules.

## Style (`tempestroid.style`)

Frozen Pydantic value objects, diffed by value.

- **`Style`** — the style model (layout, box, paint, typography, sizing,
  animation). See the grouped fields in the [styles guide](../guia/estilos.md).
- **`Color`** — `Color.from_hex("#101418")`.
- **`Edge`** — insets; `Edge.all(24.0)`.
- **`Border`** (uniform) / **`SideBorder`** (per-side).
- **`Corners`** — per-corner radii for `Style.radius`.
- **`Shadow`** — `box-shadow`/elevation.
- **`Gradient`** + **`GradientStop`** — linear gradient.
- **`Transition`** — implicit animation (`duration_ms`, `curve`, `delay_ms`).
- Enums: **`FlexDirection`**, **`JustifyContent`**, **`AlignItems`**,
  **`TextAlign`**, **`FontWeight`**, **`FontStyle`**, **`TextDecoration`**,
  **`TextOverflow`**, **`GradientDirection`**, **`Curve`**, **`ImageFit`**,
  **`KeyboardType`**.

See the [styles guide](../guia/estilos.md).

## Widgets (`tempestroid.widgets`)

The declarative IR — bare-noun widgets.

- Layout/content: **`Widget`** (base), **`Text`**, **`Button`**, **`Column`**,
  **`Row`**, **`Container`**, **`ScrollView`**, **`SafeArea`** (insets its child
  past the status/navigation bars + notch; `edges`/**`SafeAreaEdge`** selects the
  sides, default all).
- Value-bearing inputs: **`Input`** (text), **`TextArea`** (multiline),
  **`Checkbox`**, **`Switch`** (booleans), **`Slider`** (float), **`DatePicker`**
  (ISO date), **`FilePicker`** (file selection).
- Media: **`Image`**, **`Icon`**.
- Indicators: **`ProgressBar`**, **`Spinner`**.
- **`EventHandler`** — typed handler-prop wrapper.

See the [widgets guide](../guia/widgets.md).

## Events (`tempestroid.widgets`) — typed boundary contract

- **`Event`** (base), **`TapEvent`**, **`TextChangeEvent`**, **`ToggleEvent`**,
  **`SlideEvent`**, **`DateChangeEvent`**, **`FileSelectEvent`**.
- **`parse_event(event_type, raw)`** — boundary gate: validates a raw payload into
  a typed event or raises **`EventValidationError`** with structured per-field
  errors. This is the Python↔Kotlin contract for the device bridge.

See the [events guide](../guia/eventos.md).

## Core — IR + reconciler (`tempestroid.core`)

- **`Node`**, **`Path`** — the lowered IR.
- Patches: **`Insert`**, **`Remove`**, **`Update`**, **`Reorder`**, **`Replace`**,
  and the **`Patch`** union.
- **`build(widget) -> Node`**, **`diff(old, new) -> list[Patch]`**.
- **`App[S]`** — renderer-agnostic state container: holds the state, builds via
  `view(app)`, diffs, and hands patches to an `apply_patches` callback.

## Introspection (`tempestroid.core`) {#introspection}

- **`introspect()`** — the full JSON contract `{"widgets": {...}, "events":
  {...}}` (powers `tempest spec`).
- **`widget_catalog()`**, **`event_catalog()`**.

## Qt renderer (`tempestroid.renderers.qt`, needs the `qt` extra)

- **`run_qt(state, view, *, title, size)`** — run an app in the Qt simulator.
- **`run_dev(app_path)`** — the `tempest dev` cockpit.

## Device side

Compose, JNI bridge, dev server, and native capabilities — see the
[Device side (bridge)](dispositivo.md) page.
