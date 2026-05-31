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
  **`Row`**, **`Container`**, **`ScrollView`**.
- **`Component`** (base) — a composite widget that lowers to a primitive tree via
  `render()`; the reconciler expands it before diffing.
- Value-bearing inputs: **`Input`** (text), **`TextArea`** (multiline),
  **`Checkbox`**, **`Switch`** (booleans), **`Slider`** (float), **`DatePicker`**
  (ISO date), **`FilePicker`** (file selection).
- Media: **`Image`**, **`Icon`**.
- Indicators: **`ProgressBar`**, **`Spinner`**.
- **`EventHandler`** — typed handler-prop wrapper.

See the [widgets guide](../guia/widgets.md).

## Components (`tempestroid.components`)

Reusable building blocks — each a **`Component`** that lowers to primitive
widgets, so they work in both renderers (Qt and Compose) with no renderer changes
and are device-ready. Every component takes an optional `style` merged over its
default via **`merge_style`**.

- **`AppBar`** — top bar: optional `leading`, `title` and trailing `actions`.
- **`Header`** / **`Footer`** — header band (title + optional subtitle) and a
  centered bottom bar holding arbitrary `children`.
- **`Sidebar`** — fixed-`width` lateral column of `children`.
- **`Scaffold`** — page frame stacking `app_bar`, a growing `body` and an
  optional `bottom_bar` (`scroll=True` wraps the body in a `ScrollView`).
- **`NavBar`** — selectable navigation/tab bar: `items` labels, an `active` index
  and an `on_select(index)` callback (generalises the `tabs` example).
- **`Burger`** / **`Drawer`** — a hamburger menu button (☰, `on_click`) and a
  controlled lateral panel (`open` lives in app state; toggle it from the burger).
- **`Calendar`** — month grid of selectable day cells: `month` (`"YYYY-MM"`),
  `selected` (`"YYYY-MM-DD"`) and `on_select(iso_date)`.
- **`Clock`** — digital clock rendering a preformatted `time` string (the app
  drives the tick from state, as in `stopwatch`).
- **`Card`** — elevated surface (shadow + radius) grouping `children`.
- **`ListTile`** — list row: `leading` / `trailing` widgets around a `title` plus
  an optional `subtitle`.
- **`Avatar`** — round badge of short `initials`; **`Divider`** — thin rule.
- **`SegmentedControl`** / **`RadioGroup`** — single-choice pickers (`options`,
  `selected`, `on_select(index)`).
- **`Chip`** — small rounded label, selectable when given an `on_click`.
- **`Rating`** — a row of `max_stars` stars; `on_rate(value)` makes it tappable.
- **`Stepper`** — numeric `-`/`+` around a value with optional `min_value` /
  `max_value` clamping; `on_change(value)`.
- **`SearchBar`** — controlled text `Input` with an optional clear button.
- **`Accordion`** — controlled expand/collapse section (`open` in state,
  `on_toggle`).
- **`Banner`** — inline status bar (`tone`: info/success/warning/error) with an
  optional `action`; **`Badge`** — small status pill; **`EmptyState`** — centered
  glyph + title + subtitle + action.
- **`Breadcrumb`** — path trail (`items` + `separator`, optional `on_select`).
- **`Grid`** — equal-width `columns` grid of `children`.

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
