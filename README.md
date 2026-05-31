# tempestroid

Build **native Android apps** in **typed Python**.

You write one declarative, fully typed widget tree (a Pydantic IR). A
**renderer-agnostic reconciler** diffs it into patches. Two leaf renderers apply
those patches: **Qt** for the desktop simulator, **Jetpack Compose** for the
device. The runtime is **async-first**, with an Expo-style dev loop (hot restart
now, LAN code-push over QR on the roadmap).

> This is a **framework, not a web service** — no FastAPI, SQLAlchemy, Redis, or
> HTTP layering. See [`docs/plan.md`](docs/plan.md) for the full design and the
> phase roadmap.

---

## Why

- **Typed end to end.** Style model, widget primitives, events, and the
  Python↔Kotlin boundary contract are all Pydantic v2 / fully typed. `pyright`
  runs in strict mode.
- **One tree, two targets.** The reconciler is pure data-in → patches-out. All
  platform divergence is confined to the two `Style` translators (Qt today,
  Compose next).
- **Async-first.** Event handlers and lifecycle hooks may be sync or `async`;
  Python runs on a background asyncio loop, never the UI thread.
- **Fast inner loop.** `tempest dev` watches your file and hot-restarts the Qt
  simulator on save — no device or emulator needed for UI work.

---

## How it works

```text
   view(app) ──build──▶  Node tree (IR)
                              │
                            diff           pure, renderer-agnostic
                              ▼
                          [ Patch ]        Insert / Remove / Update / Reorder / Replace
                         ╱          ╲
                  Qt renderer    Compose renderer
                  (simulator)      (device, B4)
```

1. `view(app) -> Widget` builds a declarative widget tree from current state.
2. `build` lowers it to a `Node` IR; `diff` compares old vs. new and emits a
   minimal `Patch` list.
3. A renderer applies patches to live widgets. State changes coalesce into one
   rebuild per tick.

---

## Install

```bash
uv sync        # core + dev tooling + the Qt simulator
```

End users embedding the framework who want the simulator:
`pip install tempestroid[qt]`. The framework **core** needs only `pydantic` —
Qt is an optional extra.

---

## Quick start

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget
from tempestroid.renderers.qt import run_qt


@dataclass
class CounterState:
    value: int = 0


def make_state() -> CounterState:
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    return Column(
        style=Style(gap=8.0),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Button(label="+", on_click=increment, key="inc"),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(run_qt(make_state(), view, title="counter"))
```

Full example with sync **and** `async` handlers:
[`examples/counter/app.py`](examples/counter/app.py).

---

## Gallery

A set of runnable example apps lives in [`examples/`](examples/README.md). Each
exposes the same `make_state()` + `view(app)` contract, so it runs in the Qt
simulator (`uv run python examples/<name>/app.py`) **and** on a device via
code-push (`uv run tempest serve examples/<name>/app.py`) with no changes.

| App | What it shows |
|---|---|
| [`counter`](examples/counter/app.py) | Sync + `async` handlers, the basics. |
| [`todo`](examples/todo/app.py) | Type-to-add list — `Input` + `insert` / `remove` / `update` patches. |
| [`calculator`](examples/calculator/app.py) | Dense nested `Row`/`Column` button grid. |
| [`stopwatch`](examples/stopwatch/app.py) | Async loop ticking the UI via `asyncio.sleep`. |
| [`colorpicker`](examples/colorpicker/app.py) | Dynamic `Style` updates (swatches + toggles). |
| [`form`](examples/form/app.py) | All four value widgets: `Input` / `Checkbox` / `DatePicker` / `FilePicker`. |

The renderer supports `Text` / `Button` / `Column` / `Row` / `Container` plus the
value widgets `Input` / `Checkbox` / `DatePicker` / `FilePicker` (with their typed
change events) — see [`examples/README.md`](examples/README.md).

---

## CLI

```bash
uv run python examples/counter/app.py          # run an app directly in the Qt simulator
uv run tempest dev examples/counter/app.py     # dev loop: edit + save → hot restart
uv run tempest spec                            # print the typed contract (widgets/events) as JSON
uv run tempest --help
```

`tempest dev` cockpit commands: `r`/`R` (restart), `s` (status), `q` (quit). It
also auto-restarts on file save.

| Command | Status | Notes |
|---|---|---|
| `tempest dev <app>` | ✅ | Simulator + hot restart (needs `qt` extra) |
| `tempest serve <app>` | ✅ | LAN code-push to a device + log relay (phase B5) |
| `tempest spec` | ✅ | Typed widget/event contract as JSON |
| `tempest new <name>` | ✅ | Scaffold a runnable app (phase C) |
| `tempest build <app>` | ✅ | Embed the app + build an APK that runs it standalone (phase C) |
| `tempest run <app>` | ✅ | Build, install on a device, and stream logs (phase C) |

---

## Public API

Everything below is importable from the top-level `tempestroid` package.

### Style (`tempestroid.style`)

Frozen Pydantic value objects, diffed by value.

- **`Style`** — the style model (direction, gap, padding, color, font, etc.).
- **`Color`** — `Color.from_hex("#101418")`.
- **`Edge`** — insets; `Edge.all(24.0)`.
- **`Border`**.
- Enums: **`FlexDirection`**, **`JustifyContent`**, **`AlignItems`**,
  **`TextAlign`**, **`FontWeight`**.

### Widgets (`tempestroid.widgets`)

The declarative IR — bare-noun widgets.

- **`Widget`** (base), **`Text`**, **`Button`**, **`Column`**, **`Row`**,
  **`Container`**.
- Value-bearing inputs: **`Input`** (text field), **`Checkbox`**,
  **`DatePicker`**, **`FilePicker`**. Each declares a change handler
  (`on_change` / `on_select`) that receives the typed event.
- **`EventHandler`** — zero-argument handler prop wrapper. Value widgets use the
  typed variants **`TextChangeHandler`**, **`ToggleHandler`**,
  **`DateChangeHandler`**, **`FileSelectHandler`** (a handler may also be
  declared zero-argument when the value isn't needed).

### Events (`tempestroid.widgets`) — typed boundary contract

- **`Event`** (base), **`TapEvent`**, **`TextChangeEvent`**, **`ToggleEvent`**,
  **`DateChangeEvent`**, **`FileSelectEvent`**.
- **`parse_event(event_type, raw)`** — boundary gate: validates a raw payload
  into a typed event or raises **`EventValidationError`** with structured field
  errors. This is the Python↔Kotlin contract for the device bridge. The bridge
  passes the validated event to handlers that accept a positional argument.

### Core — IR + reconciler (`tempestroid.core`)

- **`Node`**, **`Path`** — the lowered IR.
- Patches: **`Insert`**, **`Remove`**, **`Update`**, **`Reorder`**,
  **`Replace`**, and the **`Patch`** union.
- **`build(widget) -> Node`**, **`diff(old, new) -> list[Patch]`**.
- **`App[S]`** — renderer-agnostic state container: owns state, builds via
  `view(app)`, diffs, hands patches to an `apply_patches` callback.

### Introspection (`tempestroid.core`)

- **`introspect()`** — full JSON contract `{"widgets": {...}, "events": {...}}`
  (powers `tempest spec`).
- **`widget_catalog()`**, **`event_catalog()`**.

### Renderer (`tempestroid.renderers.qt`, needs `qt` extra)

- **`run_qt(state, view, *, title, size)`** — run an app in the Qt simulator.
- **`run_dev(app_path)`** — the `tempest dev` cockpit.

### Compose + bridge — device side (phases B3/B4)

The Python half is device-independent and tested without a phone; the JNI
transport (B3) and the Kotlin Compose renderer (B4) are implemented in
`android-host/` and verified on a real arm64 device.

- **`to_compose(style)`** (`tempestroid.renderers.compose`) — serializable
  `Style → Compose` spec; the second `Style` translator (pairs with `Style → Qt`).
- **`serialize_node` / `serialize_patch`** — lower the IR/patches to JSON-able
  dicts (handlers → path tokens, style → Compose spec).
- **`MountMessage` / `PatchMessage` / `EventMessage`** — the wire protocol across
  the bridge: `mount` carries the full serialized tree, `patch` an incremental
  patch list, `event` a device→Python callback addressed by handler token.
- **`DeviceApp`** + **`Bridge`** / **`LoopbackBridge`** — wire an `App` to a
  device transport; the device-side analogue of `run_qt`. Events come back by
  handler token, are validated by `parse_event`, and trigger coalesced patches.
- **`JniBridge`** + **`run_device`** — the real on-device transport (phase B3):
  `JniBridge` ships messages to Kotlin via the native `_tempest_host` module;
  `run_device(state, view)` boots a `DeviceApp` on a fresh asyncio loop and
  marshals incoming events back onto it. Imports cleanly off-device (the native
  module is loaded lazily), so the framework still develops/tests on the desktop.

### Dev server — LAN code-push (phase B5)

The Expo-style on-device inner loop: edit on the dev machine, hot-restart on the
phone without rebuilding the APK (`tempest serve <app>`).

- **`DevServer`** — serves the app source (`/version`, `/app`) and relays device
  logs (`/log`) over HTTP.
- **`run_dev_client`** — the device poll loop: fetch on change → re-exec source →
  hot-restart the `DeviceApp` (transport/fetch injected, so it's desktop-testable).
- **`serve_device(url)`** — device entry point wiring the real `JniBridge` + the
  native sink + an `urllib` fetch into `run_dev_client`.
- **`render_qr(url)`** — ASCII QR for pairing (falls back to the plain URL).

### Native capabilities (phase B6)

Device-native features driven from Python as `{"kind": "native"}` commands the
Kotlin host routes to capability modules. Verified on device.

- **`notify(title, body="")`** — post a system notification from a handler.
  The extension pattern (`native_command` envelope + a host module router) is in
  place for further capabilities (camera, sensors, …).

---

## Project layout

```text
src/tempestroid/
├── style.py            # Style, Color, Edge, Border + enums (frozen Pydantic)
├── widgets/            # Widget base, Text/Button/Column/Row/Container + events.py
├── core/               # ir.py, reconciler.py, state.py, introspection.py
├── renderers/qt/       # renderer, Style→Qt, run_qt, simulator, dev_loop
├── renderers/compose/  # Style→Compose translator (device renderer, Python side)
├── bridge/             # IR/patch serialization, handler registry, DeviceApp
└── cli/                # tempest entry point + app_loader + watcher

# Trilho B (Android), outside the Python package:
docs/research/          # web research + executable B0–B6 runbook
toolchain/              # fetch CPython 3.14 + cibuildwheel native wheels
android-host/           # Gradle/Kotlin host embedding official CPython via JNI
```

---

## Status

Track A (pure desktop CPython) is **complete: A0–A6**.

| Phase | Scope | Status |
|---|---|---|
| A0 | Foundation: package, tooling, `tempest --help` | ✅ |
| A1 | Style model + typed widget primitives | ✅ |
| A2 | Reconciler: `build → diff → patch` | ✅ |
| A3 | Qt renderer: patches → `QWidget`s, `Style → Qt` | ✅ |
| A4 | Async event loop: asyncio ⨉ Qt (`qasync`) | ✅ |
| A5 | `tempest dev`: watcher, hot restart, command loop | ✅ |
| A6 | Typed event contract + introspection | ✅ |
| B0–B6 | Android runtime: CPython 3.14 arm64, native wheels, Kotlin host, JNI bridge, Compose renderer, LAN code-push, native capabilities | ✅ |
| C / D | Polish (`new`/`build`/`run`, stateful hot reload) / conformance snapshots | ⬜ |

---

## Develop

```bash
uv run ruff check .
uv run pyright          # strict mode
uv run pytest
```

Conventions: double quotes everywhere, every parameter/return/annotation typed,
Google-style English docstrings, absolute imports re-exported from each
`__init__.py`. See [`CLAUDE.md`](CLAUDE.md) for the full set.
