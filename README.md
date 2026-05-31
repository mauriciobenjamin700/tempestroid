# tempestroid

> 📖 **Documentação / Docs:** site MkDocs bilíngue em [`docs/`](docs/index.md)
> com seletor **PT-BR / EN-US** no header — rode `uv run mkdocs serve` e abra
> <http://127.0.0.1:8000> (PT) ou <http://127.0.0.1:8000/en/> (EN). Guia do
> usuário, arquitetura e referência da API.

Build **native Android apps** in **typed Python**.

You write one declarative, fully typed widget tree (a Pydantic IR). A
**renderer-agnostic reconciler** diffs it into patches. Two leaf renderers apply
those patches: **Qt** for the desktop simulator, **Jetpack Compose** for the
device. The runtime is **async-first**, with an Expo-style dev loop: hot reload
in the Qt simulator and LAN code-push to a device over QR — both shipping today.

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
| [`form`](examples/form/app.py) | The value-bearing inputs (`Input` / `Checkbox` / `DatePicker` / `FilePicker`) + their typed change events. |
| [`gallery`](examples/gallery/app.py) | The expanded set — `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView`, secure + regex + multiline text fields, and a `Style.transition`. |

The framework and the Qt simulator support the full widget set, including the
value-bearing inputs and the utility widgets (`Slider` / `Switch` /
`ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView` / `TextArea`). The
device (Compose) renderer renders `Text` / `Button` / `Column` / `Row` /
`Container` plus the value widgets `Input` / `Checkbox` / `DatePicker` /
`FilePicker` (with their typed change events); the remaining utility widgets stay
empty-box on device until the Kotlin host grows the matching cases (see
[`examples/README.md`](examples/README.md)).

---

## CLI

```bash
uv run tempest new MyApp                        # scaffold a new app project
uv run python examples/counter/app.py          # run an app directly in the Qt simulator
uv run tempest dev examples/counter/app.py     # dev loop: edit + save → hot reload (state preserved)
uv run tempest serve examples/device_counter/app.py  # push to a device over LAN, no APK rebuild
uv run tempest doctor                          # check the Android build/run prerequisites
uv run tempest build MyApp/app.py              # bundle the app into an APK
uv run tempest run MyApp/app.py                # build + install on a device + stream logs
uv run tempest spec                            # print the typed contract (widgets/events) as JSON
uv run tempest --help
```

`tempest dev` cockpit commands: `r` (hot reload, state preserved), `R` (hot
restart, clean state), `s` (raise window), `q` (quit). Saving the file
hot-reloads; a reload incompatible with the live state falls back to a clean
restart. `tempest build`/`run` drive the `android-host` Gradle project + `adb`,
so they need an Android SDK/NDK and a checkout of the host tree.

**Transparent output.** `build`/`run` announce each step (`→ … ✓/✗` with
elapsed time) and run a **preflight** first — checking the host tree, Android
SDK, `adb`, and (for `run`) a connected device — so they fail fast with an
actionable hint instead of an opaque Gradle stack trace. `tempest doctor` runs
that same preflight on its own. Pass `-v`/`--verbose` (on `build`/`run`/`dev`)
to echo the raw commands and stream the full Gradle/adb output; without it, a
failed command's tail is surfaced and the happy path stays quiet.

| Command | Status | Notes |
|---|---|---|
| `tempest new <name>` | ✅ | Scaffold a runnable app project |
| `tempest dev <app>` | ✅ | Simulator + hot reload / hot restart (needs `qt` extra); `-v` for tracebacks |
| `tempest serve <app>` | ✅ | LAN code-push to a device + log relay (phase B5) |
| `tempest spec` | ✅ | Typed widget/event contract as JSON |
| `tempest doctor` | ✅ | Check the Android build/run prerequisites (host tree, SDK, adb, device) |
| `tempest build <app>` | ✅ | Bundle an app into an APK (needs Android SDK/NDK); `-v` for full output |
| `tempest run <app>` | ✅ | Build + install on a device + stream logs; `-v` for full output |

### Running on a device from WSL

Connecting a physical Android device to a **WSL 2** session needs USB
passthrough plus an `adb` workaround for WSL's mirrored networking:

1. **Windows (admin PowerShell)** — install [usbipd-win](https://github.com/dorssel/usbipd-win)
   (`winget install usbipd`), then `usbipd bind --busid <id>` and
   `usbipd attach --wsl --busid <id>` (find `<id>` via `usbipd list`).
2. **Device** — enable USB debugging; on MIUI/HyperOS also enable **"Install via
   USB"** (else `adb install` fails `INSTALL_FAILED_USER_RESTRICTED`).
3. **WSL** — under mirrored networking `adb start-server` hangs; start it in the
   foreground instead and leave it running:
   `adb nodaemon server &`, then `adb devices` responds normally.
4. Build + install: `ANDROID_SDK_ROOT=/usr/lib/android-sdk make apk-install`
   (Gradle wrapper 8.11.1).

Full walkthrough + troubleshooting: **[Running on a device (WSL)](docs/guia/dispositivo-wsl.md)**.

---

## Public API

Everything below is importable from the top-level `tempestroid` package.

### Style (`tempestroid.style`)

Frozen Pydantic value objects, diffed by value.

- **`Style`** — the style model (layout, box model, paint, typography, sizing,
  effects, animation). Notable fields: `opacity`, `shadow`, `align_self`,
  `letter_spacing`, `line_height`, `max_lines`, `text_overflow`, `aspect_ratio`.
- **`Color`** — `Color.from_hex("#101418")`.
- **`Edge`** — insets; `Edge.all(24.0)`.
- **`Border`** (uniform) / **`SideBorder`** (per-side, e.g. a bottom divider).
- **`Corners`** — per-corner radii for `Style.radius` (e.g. top-rounded sheets).
- **`Shadow`** — `box-shadow` / elevation (`color` / `blur` / `offset_x` /
  `offset_y`); Compose maps it to elevation, Qt to a `QGraphicsDropShadowEffect`.
- **`Gradient`** + **`GradientStop`** — a linear gradient usable wherever a
  background `Color` is (QSS `qlineargradient` / Compose `Brush`).
- **`Transition`** — implicit animation (`duration_ms` / `curve` / `delay_ms`):
  on rebuild the renderer tweens changed visual props instead of snapping
  (Compose maps it to `animate*AsState`; Qt animation is renderer-imperative).
- Enums: **`FlexDirection`**, **`JustifyContent`**, **`AlignItems`**,
  **`TextAlign`**, **`FontWeight`**, **`FontStyle`**, **`TextDecoration`**,
  **`TextOverflow`**, **`GradientDirection`**, **`Curve`** (easing).

### Widgets (`tempestroid.widgets`)

The declarative IR — bare-noun widgets.

- **`Widget`** (base), **`Text`**, **`Button`**, **`Column`**, **`Row`**,
  **`Container`**, **`ScrollView`** (scrollable container).
- **`Component`** (base) — a composite widget that lowers to a primitive tree via
  `render()`; the reconciler expands it before diffing, so renderers never see it.
- Value-bearing inputs: **`Input`** (text — with `secure` password masking +
  reveal toggle, regex `pattern`, `keyboard` type, `max_length`), **`TextArea`**
  (multi-line), **`Checkbox`** (boolean), **`Switch`** (boolean toggle),
  **`Slider`** (numeric range), **`DatePicker`** (ISO date), **`FilePicker`**
  (file selection).
- Presentation widgets: **`Image`** (URL/asset, `fit`), **`Icon`** (named glyph),
  **`ProgressBar`** (determinate/indeterminate), **`Spinner`** (activity).
- Enums: **`KeyboardType`** (text/number/email/phone/url/password),
  **`ImageFit`** (contain/cover/fill/none).
- **`EventHandler`** — the typed handler-prop wrapper used by every handler field
  (`on_click`, `on_change`, `on_select`); sync or `async`, zero- or one-argument.

### Components (`tempestroid.components`)

Higher-level, reusable building blocks — each a **`Component`** that lowers to
primitive widgets, so they work in both renderers (Qt and Compose) with zero
renderer changes and are fully device-ready. Every component takes an optional
`style` that is merged over its default via **`merge_style`**.

- **`AppBar`** — top bar: optional `leading` widget, `title`, trailing `actions`.
- **`Header`** / **`Footer`** — page header band (title + optional subtitle) and
  a centered bottom bar holding arbitrary `children`.
- **`Sidebar`** — fixed-`width` lateral column of `children`.
- **`Scaffold`** — page frame stacking `app_bar`, a growing `body` and an
  optional `bottom_bar` (set `scroll=True` to wrap the body in a `ScrollView`).
- **`NavBar`** — selectable navigation/tab bar: `items` labels, an `active`
  index and an `on_select(index)` callback (generalises the `tabs` example).
- **`Burger`** / **`Drawer`** — a hamburger menu button (`on_click`) and a
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
  glyph + title + subtitle + action placeholder.
- **`Breadcrumb`** — path trail (`items` + `separator`, optional `on_select`).
- **`Grid`** — equal-width `columns` grid of `children`.

### Events (`tempestroid.widgets`) — typed boundary contract

- **`Event`** (base), **`TapEvent`**, **`TextChangeEvent`** (carries `valid`
  against the input's `pattern`), **`ToggleEvent`**, **`SlideEvent`**,
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

### Native capabilities (phase B6+)

Device-native features driven from Python as `{"kind": "native"}` commands the
Kotlin host routes to capability modules. Two shapes share the one JNI channel:
**fire-and-forget** (one-way) and **request/response** (`await` a result; the
host replies over the event channel under a reserved token — no extra native
entry point). A failed request/response call raises `NativeError` carrying a
machine-readable `code` (`permission_denied` / `cancelled` / `not_found` /
`unavailable` / `io_error`). Permissions (location, camera, bluetooth) are
requested on demand by the host.

Fire-and-forget:

- **`notify(title, body="")`** — post a system notification.
- **`share(text="", url="", title="")`** — open the system share sheet.
- **`share_to_whatsapp(text="", phone="")`** — share to WhatsApp (`wa.me`,
  optional E.164 number).
- **`open_url(url)`** — open a URL with the default handler.
- **`set_text(text)`** — write to the clipboard.

Request/response (`async`, awaited from a handler):

- **`await get_position(high_accuracy=True) -> Position`** — a single location
  fix (`latitude`/`longitude`/`accuracy`/`altitude`).
- **`await take_photo() -> Photo`** — capture a photo (`path`/`width`/`height`).
- **`await read_file(name)` / `write_file(name, content)` / `delete_file(name)`
  / `list_files() -> list[str]`** — app-private device storage.
- **`await get_text() -> str`** — read the clipboard.
- **`await scan(timeout=8.0) -> list[BluetoothDevice]`** — discover nearby
  Bluetooth devices (`address`/`name`/`rssi`).

```python
from tempestroid import App, Button, Text, Widget
from tempestroid.native import get_position, share, NativeError

async def _locate(app: App[State]) -> None:
    try:
        pos = await get_position()
        app.set_state(lambda s: setattr(s, "label", f"{pos.latitude}, {pos.longitude}"))
    except NativeError as exc:
        app.set_state(lambda s: setattr(s, "label", f"erro: {exc.code}"))
```

The `native_command` / `native_request` envelope + the host module router is the
extension point for further capabilities (sensors, contacts, …). The Python side
(envelopes, pending-future resolution, typed results) is fully unit-tested
off-device; the Kotlin capability modules need an Android device to validate.

---

## Project layout

```text
tempestroid/
├── style.py            # Style + value objects (Color/Edge/Border/Corners/Shadow/Gradient/Transition) + enums (frozen Pydantic)
├── widgets/            # Widget base + Component base + layout/inputs/media/indicators widgets + events.py
├── components/         # composite components (AppBar/Header/Footer/Sidebar/Scaffold/NavBar)
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
| C | Polish: `new`/`build`/`run` + stateful hot reload | ✅ |
| D | Conformance golden snapshots (Qt vs Compose) | ✅ |

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
