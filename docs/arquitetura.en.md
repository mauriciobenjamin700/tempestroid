# Architecture

tempestroid separates **what to render** (a typed, serializable IR) from **how to
render** (per-platform leaf renderers), tied together by a **pure reconciler**.

## Invariants

- **The reconciler is renderer-agnostic** — pure data in, patches out. All
  platform divergence is confined to the two `Style` translators.
- **The widget tree is the IR** — serializable Pydantic models. Walk any tree via
  `Widget.child_nodes()`; never reach into renderer-specific child storage.
- **Python runs on a background thread** hosting an asyncio loop, never the UI
  thread. Marshalling crosses a single bridge boundary.

## The pipeline

```text
   view(app) ──build──▶  Node tree (IR)
                              │
                            diff
                              ▼
                          [ Patch ]
                         ╱          ╲
                  Qt renderer      Compose renderer
```

### 1. Widgets (the IR)

`view(app)` returns a `Widget` tree — Pydantic models, frozen where they
represent immutable values. Each widget is a declarative node: `Text`, `Button`,
`Column`, `Row`, `Container`, `ScrollView`, the value-bearing inputs (`Input`,
`TextArea`, `Checkbox`, `Switch`, `Slider`, `DatePicker`, `FilePicker`, …), plus
media, indicators, and dozens more (virtualized lists, navigation, overlays,
animation, gestures) — all supported by **both renderers**. The full list is in
the [examples guide](guia/exemplos.md#current-widget-set).

### 2. build → Node

`build(widget) -> Node` lowers the widget tree to the `Node` IR: a uniform
structure with `type`, `key`, `props`, and `children`. This is the shape the
reconciler and the serializers understand.

### 3. diff → Patch

`diff(old, new) -> list[Patch]` compares two `Node` trees and emits the minimal
patch list:

| Patch | Meaning |
|---|---|
| `Insert` | Insert a new node at a position. |
| `Remove` | Remove a node. |
| `Update` | Update a node's `props` (fields to set / unset). |
| `Reorder` | Reorder children (pure key permutation only). |
| `Replace` | Swap a node for one of a different type. |

!!! note "Child diffing is positional by default"
    A single `Reorder` is only emitted for a *pure permutation* (both lists fully
    keyed, unique keys, same set, equal length). Mixed insert + reorder falls back
    to positional — correct, but less optimal.

### 4. Renderers apply patches

Each leaf renderer applies the same patches to its live widgets:

- **Qt** (`renderers/qt`) — maps `Node`s to `QWidget`s and `Style` to
  `QBoxLayout` + QSS. The desktop simulator.
- **Compose** (`renderers/compose` + the Kotlin host) — maps the serialized tree
  to `@Composable`s and `Style` to `Modifier`/`Arrangement`/`Alignment`. The
  device renderer.

## Simulator fidelity (what it reflects — and what it doesn't)

The Qt simulator is a **faithful semantic proxy**, not a pixel-perfect mirror of
the device. Knowing the boundary lets you trust it where it counts.

**What is identical** (the backbone): the same IR tree, the same reconciler, the
same `view → diff → patch` flow, the same typed events and the same coalesced
state. Layout, navigation, logic, state and events behave the same. Most `Style`
fields are honored on both (alignment, `SPACE_*` spacing, `STRETCH`, `text_align`,
fixed size, padding/margin, color, font). The simulator's sizes are in **dp** —
the same layout space Compose uses — so what fits in the window fits on the device
(see [pick the screen size](inicio-rapido.md#pick-the-screen-size-device-presets)).

!!! check "Parity guarantee"
    The **conformance** suite (`tests/conformance/`) pins **both `Style`
    translators side by side** (golden snapshots of `to_qss` and `to_compose`) +
    a per-field coverage table. They **cannot silently diverge** — a change that
    regresses parity breaks the gate.

**What only the device shows faithfully** (expected divergences):

- **Widget appearance** — Qt uses QWidget/QSS; the device uses **Material 3**.
  Dialogs, menus, bottom sheets, pickers and fields wear each platform's native
  look.
- **Animations** — Qt uses `QPropertyAnimation`; the device drives Compose's
  native engine (`animate*AsState`/`AnimatedContent`).
- **Overlays & safe-area** — Compose manages its own
  `WindowInsets.safeDrawing`/scrim; Qt approximates with a manual scrim.
- **Fonts & OS density** shift fine layout metrics.
- **Hardware widgets** — `CameraPreview`/`QrScanner`/`MapView` are **device-only**;
  the simulator shows a signalled placeholder.

!!! warning "Rule: dual verification"
    So when you touch UI surface, validate on **both**: the Qt simulator **and**
    the physical device (Compose) when one is connected — `make dual-verify`. The
    simulator speeds up development; the device confirms final appearance,
    animations and overlays.

## State: `App[S]`

`App[S]` is the renderer-agnostic state container. It:

- holds the state (`app.state`);
- builds the UI via the `view(app)` function;
- diffs and hands the patches to an `apply_patches` callback.

Rebuilds are **coalesced**: `request_rebuild` schedules a single `_rebuild` via
`loop.call_soon`, so many `set_state` calls in one tick produce one diff. No-op
rebuilds emit no patches.

## The typed boundary (Python↔Kotlin)

Without a WebView there is no JS↔Python frontier; the typed contract lives at the
Python↔Kotlin boundary. Events coming back from the native side (a tap, a text
change) arrive as raw payloads and are **validated before** entering a handler —
exactly like FastAPI validates a request body.

- `parse_event(event_type, raw)` is the validation gate: it turns a raw payload
  into a typed event or raises `EventValidationError` with structured per-field
  errors.
- Serialization (`serialize_node` / `serialize_patch`) lowers the IR/patches to
  JSON-able dicts: handlers become path tokens, `Style` becomes the Compose spec.

See [Device side (bridge)](referencia/dispositivo.md) for the wire protocol and
the JNI transport.

## Recap

- tempestroid separates **what** to render (the widget IR) from **how** (leaf
  renderers), linked by a pure reconciler.
- The pipeline: `view → build → diff → patches → renderer`.
- `App[S]` holds state and coalesces rebuilds (one diff per tick).
- The Python↔Kotlin boundary is typed and validated (`parse_event`,
  `serialize_node`).

## Next steps

➡️ Meet the primitives in **[Widgets](guia/widgets.md)**, or dig into the bridge
in **[Device side](referencia/dispositivo.md)**.
