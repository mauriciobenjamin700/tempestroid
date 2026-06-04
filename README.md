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

The framework and the Qt simulator support the full widget set. The device
(Compose) renderer renders `Text` / `Button` / `Column` / `Row` / `Container` /
`SafeArea` (insetting against the real `WindowInsets.safeDrawing`) / `Stack` /
`GestureDetector`, the value widgets `Input` / `TextArea` / `Checkbox` /
`Switch` / `Slider` / `DatePicker` / `FilePicker` (with their typed change
events), and the presentation/utility widgets `ProgressBar` / `Spinner` /
`Image` (via Coil) / `Icon` (named Material icons) / `ScrollView`. See
[`examples/README.md`](examples/README.md).

---

## CLI

```bash
uv run tempest new .                # scaffold a fully configured project in the current dir
uv run tempest dev                  # dev loop: edit + save → hot reload (reads pyproject)
uv run tempest install              # download + adb-install the prebuilt host (no SDK/NDK)
uv run tempest serve                # push to a device over LAN + auto-launch in dev mode
uv run tempest doctor               # check the Android build/run prerequisites
uv run tempest build                # bundle the app into an APK (from-source; needs SDK/NDK)
uv run tempest run                  # build + install on a device + stream logs
uv run tempest spec                 # print the typed contract (widgets/events) as JSON
uv run tempest --version            # print the framework version (also: tempest version)
uv run tempest --help
```

`tempest new <name>` makes a new subdirectory; `tempest new .` scaffolds in the
current directory. The generated `pyproject.toml` carries `[tool.tempest] app =
"app.py"`, so **`dev` / `serve` / `build` / `run` take no app argument inside a
project** — pass an explicit path (`tempest dev path/to/app.py`) only to override.

`tempest dev` cockpit commands: `r` (hot reload, state preserved), `R` (hot
restart, clean state), `s` (raise window), `q` (quit). Saving the file
hot-reloads; a reload incompatible with the live state falls back to a clean
restart.

**Running on a device — the easy path (no toolchain).** You do **not** need an
Android SDK/NDK or the `android-host` source to run on hardware. Install the
prebuilt host once, then push your Python over LAN:

```bash
uv run tempest install   # fetch + adb-install the prebuilt host APK
uv run tempest serve     # auto adb-reverse + launches the host in dev mode
```

`tempest install` resolves the host APK in order: an explicit `.apk` path/URL →
`TEMPESTROID_HOST_APK` → a bundled asset (present in source checkouts) → a
download from the matching GitHub release (`TEMPESTROID_HOST_APK_URL` to override),
cached under `~/.cache/tempestroid` so it's fetched only once. With a device
connected, `tempest serve` wires `adb reverse` and launches the host in dev mode
pointing at the dev server, so edit-and-save hot-reloads on the device — no APK
rebuild. Use `--no-launch` to serve only.

**Building an APK from source** (`tempest build`/`run`) is the maintainer path:
it drives the `android-host` Gradle project + `adb`, so it needs an Android
SDK/NDK **and** a checkout of the host tree. From an installed wheel it fails
fast with a hint pointing at `tempest install` + `tempest serve`.

> **Maintainers:** publish the host APK to the GitHub release for each version
> with `make publish-host` (builds via `make apk` first, then `gh release
> upload`), so `tempest install` resolves it as a download. Optionally
> `make stage-host` copies it to `tempestroid/_assets/host.apk` (gitignored) for
> a local checkout to install offline; the PyPI wheel stays lean.

**Transparent output.** `build`/`run` announce each step (`→ … ✓/✗` with
elapsed time) and run a **preflight** first — checking the host tree, Android
SDK, `adb`, and (for `run`) a connected device — so they fail fast with an
actionable hint instead of an opaque Gradle stack trace. `tempest doctor` runs
that same preflight on its own. Pass `-v`/`--verbose` (on `build`/`run`/`dev`)
to echo the raw commands and stream the full Gradle/adb output; without it, a
failed command's tail is surfaced and the happy path stays quiet.

| Command | Status | Notes |
|---|---|---|
| `tempest new [name]` | ✅ | Scaffold a fully configured project (`.` = current dir); writes `pyproject.toml` + `app.py` + `.gitignore` |
| `tempest dev [app]` | ✅ | Simulator + hot reload / hot restart (needs `qt` extra); app from `[tool.tempest]` when omitted; `-v` for tracebacks |
| `tempest serve [app]` | ✅ | LAN code-push to a device + log relay; auto `adb reverse` + launch in dev mode (`--no-launch` to skip) |
| `tempest install [src]` | ✅ | Fetch + adb-install the prebuilt host APK (no SDK/NDK); resolves `src`/env/bundled/GitHub-release (cached); `src` = local `.apk`/URL |
| `tempest spec` | ✅ | Typed widget/event contract as JSON |
| `tempest doctor` | ✅ | Check the Android build/run prerequisites (host tree, SDK, adb, device) |
| `tempest build <app>` | ✅ | Bundle an app into an APK (needs Android SDK/NDK); `-v` for full output |
| `tempest run <app>` | ✅ | Build + install on a device + stream logs; `-v` for full output |
| `tempest version` | ✅ | Print the framework version (alias of the global `--version`/`-V`) |

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
  **`TextOverflow`**, **`GradientDirection`**, **`Curve`** (easing),
  **`StackAlign`** (overlay child alignment in a `Stack`).

### Widgets (`tempestroid.widgets`)

The declarative IR — bare-noun widgets.

- **`Widget`** (base), **`Text`**, **`Button`**, **`Column`**, **`Row`**,
  **`Container`**, **`ScrollView`** (scrollable container), **`SafeArea`**
  (insets its child past the status/navigation bars + notch; `edges` selects
  which sides, default all — `SafeAreaEdge` enum).
- **`Stack`** — overlay/z-order container: children share one box, layered in
  declaration order. A child with `position=ABSOLUTE` is anchored by its
  `top`/`right`/`bottom`/`left` insets; the rest align by `Style.stack_align`
  (`StackAlign` enum). The framework's overlay primitive (scrim, modal, FAB).
- **`GestureDetector`** — wraps a `child` and reports pointer gestures via
  **`TapHandler`** / **`LongPressHandler`** / **`SwipeHandler`** props
  (`on_tap` / `on_double_tap` / `on_long_press` / `on_swipe`).
- Navigation hosts — render the `NavStack` into a tree (a route change diffs to
  an `Update`/`Replace`, no new patch kind): **`Navigator`** (stack host: shows
  the top `child`, `transition` slide/fade/none + `depth` drive the animation),
  **`TabView`** (tab strip + active tab `child`), **`TabBar`** (standalone tab
  strip), **`RouteDrawer`** (main `child` + a slide-over `drawer` panel toggled
  by `open`). Each emits **`RouteChangeEvent`** via an **`on_change`**
  (**`RouteChangeHandler`**) prop. In the Qt simulator `Esc` maps to back
  (`App.pop`); the device back button is the Compose/device half.
- **`Component`** (base) — a composite widget that lowers to a primitive tree via
  `render()`; the reconciler expands it before diffing, so renderers never see it.
- Value-bearing inputs: **`Input`** (text — with `secure` password masking +
  reveal toggle, regex `pattern`, `keyboard` type, `max_length`), **`TextArea`**
  (multi-line), **`Checkbox`** (boolean), **`Switch`** (boolean toggle),
  **`Slider`** (numeric range), **`DatePicker`** (ISO date), **`FilePicker`**
  (file selection).
- Presentation widgets: **`Image`** (URL/asset, `fit`), **`Icon`** (named glyph),
  **`ProgressBar`** (determinate/indeterminate), **`Spinner`** (activity).
- Virtualized lists (only the visible window is materialized; declare an
  `item_count` + an `item_builder(index) -> Widget`, never a static child list):
  **`LazyColumn`** / **`LazyRow`** (vertical/horizontal lazy lists),
  **`LazyGrid`** (`columns`-wide lazy grid), **`SectionList`** (a list of
  **`SectionHeader`** sections with sticky headers) and **`RefreshControl`**
  (standalone pull-to-refresh). The widgets materialize their **initial window**
  at `build` time — `child_nodes()` builds the items in `window` (when set) or the
  first `window_size` items (default **`DEFAULT_WINDOW_SIZE`** = 20), each keyed by
  its absolute index — so the very first mount has content. The app slides the
  window with `App.slide_window(key, start, end)` (and
  `App.slide_section_window(key, title, start, end)` for sections) from a scroll
  handler; the keyed diff turns a slide into a minimal remove/reorder/insert. They
  emit **`ScrollEvent`** (`on_scroll`), **`RefreshEvent`** (`on_refresh`) and
  **`EndReachedEvent`** (`on_end_reached`, fired past `end_reached_threshold` —
  wire it to paginate). The matching handler aliases are **`ScrollHandler`** /
  **`RefreshHandler`** / **`EndReachedHandler`**.
- Overlay + feedback widgets (pushed onto the floating overlay layer via the
  `App` overlay API, not nested in the screen tree): **`Dialog`** (modal, optional
  `title` + body `children`, `on_dismiss`), **`BottomSheet`** (`children`,
  `on_dismiss`), **`Toast`** (transient `message` + `duration_s`, auto-dismisses),
  **`Tooltip`** (`message` + optional `child`), **`Menu`** (selectable
  **`MenuItem`** `items`, optional `anchor` key, `on_select`), **`Popover`**
  (anchored `child`, `on_dismiss`) and **`ActionSheet`** (titled `items`,
  `on_select`). `MenuItem` is a frozen value model (`label` / `value` / `icon`)
  that crosses the bridge as plain JSON. The matching handler aliases are
  **`DismissHandler`** and **`MenuSelectHandler`**.
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
- Gesture events (from `GestureDetector`): **`LongPressEvent`** (optional
  `x`/`y`), **`SwipeEvent`** (`direction` + `dx`/`dy`) with the
  **`SwipeDirection`** enum (left/right/up/down).
- **`RouteChangeEvent`** (`name` + typed `params`) — emitted when navigation
  settles on a new route.
- Virtualized-list events: **`ScrollEvent`** (`offset` + `direction`),
  **`RefreshEvent`** (pull-to-refresh) and **`EndReachedEvent`** (threshold
  reached) — emitted by `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` /
  `RefreshControl`.
- Overlay events: **`DismissEvent`** (optional `overlay_id`) — an overlay
  dismissed by a host-owned gesture (`Dialog` / `BottomSheet` / `Popover`); and
  **`MenuSelectEvent`** (`value` + `label`) — a `Menu` / `ActionSheet` selection.
- **`parse_event(event_type, raw)`** — boundary gate: validates a raw payload
  into a typed event or raises **`EventValidationError`** with structured field
  errors. This is the Python↔Kotlin contract for the device bridge. The bridge
  passes the validated event to handlers that accept a positional argument.

### Core — IR + reconciler (`tempestroid.core`)

- **`Node`**, **`Path`** — the lowered IR. `Path` is `tuple[int | str, ...]`: a
  child-index path, except the reserved leading `"overlay"` token that addresses
  the overlay layer (`("overlay", i, …)`).
- **`Scene`** — a full UI document: a `root` node plus an ascending z-order
  `overlays` layer (each overlay node keyed by its stable overlay id).
- Patches: **`Insert`**, **`Remove`**, **`Update`**, **`Reorder`**,
  **`Replace`**, and the **`Patch`** union. Overlays reuse these — no new kind.
- **`build(widget) -> Node`**, **`diff(old, new) -> list[Patch]`**,
  **`build_scene(widget, overlays) -> Scene`** (overlays as `(id, widget,
  barrier)` tuples), **`diff_scene(old, new) -> list[Patch]`** (root diffed as
  before; overlays diffed keyed under the `("overlay", …)` prefix).
- **`App[S]`** — renderer-agnostic state container: owns state, builds via
  `view(app)` into a `Scene` (root tree + overlay layer), diffs, hands patches to
  an `apply_patches` callback. `App.start()` returns the `Scene` and
  `App.current_tree` is the live `Scene`. It also owns a `NavStack` (`app.nav`)
  and exposes navigation helpers: **`push(route)`** / **`pop() -> bool`** /
  **`replace(route)`** / **`reset(stack)`** — each mutates the stack and schedules
  the same coalesced rebuild (no new patch kind). `pop()` returns `False` at the
  root.
- Overlay API (imperative, returns a stable overlay id for `dismiss`):
  **`show_dialog(widget, *, barrier=True)`**, **`show_sheet(widget, *,
  barrier=True)`**, **`show_menu(widget, *, anchor=None, barrier=False)`**,
  **`toast(widget, *, duration_s=2.5)`** (auto-dismisses via `loop.call_later`)
  and **`dismiss(overlay_id)`**. Each schedules the same coalesced rebuild;
  **`OverlayEntry`** is the internal overlay slot.

### Navigation (`tempestroid`)

- **`Route`** — a frozen navigation destination: `name` + typed `params`.
- **`NavStack`** — the mutable route stack (defaults to `[Route(name="/")]`);
  `top` is the visible screen and `can_pop` is `True` past the root. The stack is
  not a new IR node — `view(app)` reads `app.nav.top` to build the current
  screen, so changing routes diffs through the existing reconciler.
- **`routes_from_path(path) -> list[Route]`** — resolve a deep-link path into an
  initial stack (`"/a/b"` → `["/", "/a", "/a/b"]`, so back pops through the
  intermediate screens). The entry point hands the result to `App.reset` so a
  deep link opens directly on the linked screen with its back stack built.

### Introspection (`tempestroid.core`)

- **`introspect()`** — full JSON contract `{"widgets": {...}, "events": {...}}`
  (powers `tempest spec`).
- **`widget_catalog()`**, **`event_catalog()`**.

### Renderer (`tempestroid.renderers.qt`, needs `qt` extra)

- **`run_qt(state, view, *, title, size)`** — run an app in the Qt simulator.
- **`run_dev(app_path)`** — the `tempest dev` cockpit.

### Device presets (`tempestroid.devices`)

Logical (`dp`) viewport sizes for common Android phones, so the simulator window
can match a real device instead of a generic guess.

- **`Device`** — `Enum` of presets (Pixel, Galaxy S/A, Redmi / Redmi Note, Poco,
  Xiaomi, Moto, OnePlus). Each member carries `width` / `height` (in `dp`) and a
  human `label`; `.size` returns the `(width, height)` tuple.
- **`DEFAULT_DEVICE`** — the simulator default (`Device.REDMI_NOTE_12`, 393×873 dp).

```python
from tempestroid import Device, run_qt

run_qt(state, view, size=Device.GALAXY_S23.size)
```

### Compose + bridge — device side (phases B3/B4)

The Python half is device-independent and tested without a phone; the JNI
transport (B3) and the Kotlin Compose renderer (B4) are implemented in
`android-host/` and verified on a real arm64 device.

- **`to_compose(style)`** (`tempestroid.renderers.compose`) — serializable
  `Style → Compose` spec; the second `Style` translator (pairs with `Style → Qt`).
- **`serialize_node` / `serialize_patch`** — lower the IR/patches to JSON-able
  dicts (handlers → path tokens, style → Compose spec).
- **`MountMessage` / `PatchMessage` / `EventMessage`** — the wire protocol across
  the bridge: `mount` carries the full serialized tree (plus an `overlays` list of
  serialized overlay nodes), `patch` an incremental patch list (overlay patches
  ride under the `("overlay", …)` path), `event` a device→Python callback
  addressed by handler token. `mount`/`patch` also carry **`can_pop`** (the live
  `app.nav.can_pop`), so the host can gate its system-back handler without a
  round-trip.
- **`BACK_TOKEN`** (`"__back__"`) — the reserved event token the host sends on a
  system back action (e.g. the Android back gesture). The bridge routes it
  straight to `App.pop` (no widget handler, no new JNI entry) — it pops a screen,
  or is a no-op at the root where the host's default close-the-app action runs.
- **`DISMISS_TOKEN_PREFIX`** (`"__dismiss__"`) — the reserved event-token prefix
  the host sends when an overlay is dismissed by a host-owned gesture (scrim tap,
  swipe-down): `"__dismiss__:<overlay_id>"`. The bridge strips the prefix and
  routes the id to `App.dismiss` (no widget handler, no new JNI entry).
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
- **`await take_photo(*, camera=CameraFacing.BACK, max_width=None, max_height=None) -> Photo`**
  — capture a photo (`path`/`width`/`height`); the host downscales to the size caps.
- **`await record_video(*, camera=CameraFacing.BACK, max_duration_s=None, quality=VideoQuality.HIGH) -> Video`**
  — record a clip (`path`/`duration_ms`/`width`/`height`).
- **`await record_audio(*, max_duration_s=None) -> AudioClip`** — record from the
  microphone (`path`/`duration_ms`).
- **`await play_sound(src, *, volume=1.0)` / `stop_sound()`** — play/stop audio on
  the device speaker (`src` = local path or URL).
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
