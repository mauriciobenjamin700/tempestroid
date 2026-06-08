# tempestroid

> 📖 **Documentação / Docs:** site MkDocs bilíngue em [`docs/`](docs/index.md)
> com seletor **PT-BR / EN-US** no header — rode `uv run mkdocs serve` e abra
> <http://127.0.0.1:8000> (PT) ou <http://127.0.0.1:8000/en/> (EN). Guia do
> usuário, arquitetura e referência da API.
>
> 🤖 **Ler com sua IA / Read with your AI:** o site publica
> [`/llms.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms.txt) (índice)
> e [`/llms-full.txt`](https://mauriciobenjamin700.github.io/tempestroid/llms-full.txt)
> (docs inteiras num arquivo) seguindo a convenção [llmstxt.org](https://llmstxt.org/) —
> entregue a URL ao seu assistente para usar o projeto como referência (sem servidor/MCP).

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

**Building an app?** Install from PyPI — the **core** needs only `pydantic`:

```bash
pip install tempestroid            # core
pip install "tempestroid[qt]"      # + desktop simulator (PySide6 + qasync)
pip install "tempestroid[icons]"   # + tempest icon (Pillow)
```

Building the Android **APK** (`tempest build apk`) needs only a **JDK + Android
SDK** (no NDK, no CPython toolchain, no repo clone — the `android-host` ships in
the package). Run `tempest setup --install` to get the SDK and `tempest doctor`
to check what's missing.

**Contributing to the framework?** Clone this repo and use `uv` — one command
installs the core + dev tooling + Qt simulator + docs:

```bash
uv sync
```

See the [installation guide](https://mauriciobenjamin700.github.io/tempestroid/instalacao/)
([EN](https://mauriciobenjamin700.github.io/tempestroid/en/instalacao/)) for the
full breakdown.

---

## Quick start

```python
from dataclasses import dataclass

from tempestroid import App, Button, Column, Style, Text, Widget


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
    # Import the Qt renderer lazily — keep the module Qt-free so the SAME file
    # also loads on the Android device (which has no PySide6). A top-level
    # `from tempestroid.renderers.qt import run_qt` would crash the on-device
    # load; the framework now shows an error screen instead of a blank window,
    # but the fix is to import Qt only where you run the desktop simulator.
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(run_qt(make_state(), view, title="counter"))
```

> 💡 The module above only ever imports `tempestroid` (renderer-agnostic) at the
> top level — `run_qt` is imported lazily inside `__main__`. That is what lets
> the same `make_state()` + `view(app)` run in the Qt simulator **and** on a
> device via `tempest serve` with no changes. If an app file (or one of its
> imports) fails to load on the device, the host now renders a red **error
> screen** carrying the traceback instead of a silent white window.

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
| [`forms`](examples/forms/app.py) | A validating `Form` of `FormField`s (typed validators block an invalid submit, per-field error inline) + `Dropdown` + `PinInput` OTP. |
| [`gallery`](examples/gallery/app.py) | The expanded set — `Slider` / `Switch` / `ProgressBar` / `Spinner` / `Image` / `Icon` / `ScrollView`, secure + regex + multiline text fields, and a `Style.transition`. |
| [`layout`](examples/layout/app.py) | Refined layout — `Wrap` chips that wrap, a paginated `PageView` (`PageChangeEvent` + dot indicator) and a `CollapsingAppBar` that shrinks on scroll. |
| [`platform`](examples/platform/app.py) | Platform/system (E8) — haptics, real preferences, the lifecycle stream and a `KeyboardAvoidingView`. |
| [`theming`](examples/theming/app.py) | Cross-cutting (E9) — a light/dark `ThemeMode` toggle (`App.set_theme`), a PT↔AR locale/RTL toggle (`App.set_locale` + `translate`), and a counter label carrying `Semantics(label=…)`. |
| [`native_caps`](examples/native_caps/app.py) | Native capabilities — `clipboard` / `storage` / `database` (SQLite) / `secure_storage` / `system`, each a request/response round-trip returning a typed result (device-verified). |

**Both renderers** — the Qt simulator and Compose on the device — support the
full Track E widget set (~70 types): layout, text & action, the value-bearing
inputs (`Input` / `TextArea` / `Checkbox` / `Switch` / `Slider` / `RangeSlider`
/ `Dropdown` / `DatePicker` / `TimePicker` / `FilePicker` / `PinInput` /
`MaskedInput` / `Autocomplete` / `Form`) with their typed change events,
virtualized lists, navigation, overlays, animation, gestures, and media. Parity
is pinned by the conformance suite (golden snapshots of both `Style` translators)
and device-verified across E0–E9. A few hardware widgets (`CameraPreview` /
`QrScanner` / `MapView`) are device-only and show a signalled placeholder on Qt.
See the [widget set](https://mauriciobenjamin700.github.io/tempestroid/guia/exemplos/#conjunto-de-widgets-atual)
and [`examples/README.md`](examples/README.md).

---

## CLI

```bash
uv run tempest new                  # scaffold in the CURRENT dir (id = folder name)
uv run tempest dev                  # dev loop: edit + save → hot reload (reads pyproject)
uv run tempest dev -d pixel-7       # …sized to a device preset (dp; matches Compose)
uv run tempest install              # download + adb-install the prebuilt host (no SDK/NDK)
uv run tempest deploy               # push the whole project to a device — offline, no SDK/NDK
uv run tempest serve                # LAN code-push + hot reload (whole project) in dev mode
uv run tempest doctor               # check the Android build/run prerequisites
uv run tempest build apk            # per-app APK (own id, installs side by side); reads [tool.tempest]; JDK+SDK
uv run tempest build prd            # store-ready release AAB (Play); reads [tool.tempest] + keystore
uv run tempest run                  # build + install on a device + stream logs (needs SDK/NDK)
uv run tempest icon logo.png        # generate icon.png + splash.png from one image (needs [icons])
uv run tempest spec                 # print the typed contract (widgets/events) as JSON
uv run tempest --version            # print the framework version (also: tempest version)
uv run tempest --help
```

Run `tempest new` **inside your already-created project folder** (and venv): it
scaffolds in place and uses the **folder name as the app id** — no extra wrapping
directory. Pass a name (`tempest new other`) only if you want a new subdirectory.
The generated `pyproject.toml` carries `[tool.tempest] app = "app.py"`, so
**`dev` / `serve` / `build` / `run` take no app argument inside a project** —
pass an explicit path (`tempest build path/to/app.py`) only to override.

Pick a starting structure with `--template`/`-t`:

- `default` (the default) — a single `app.py`, great for a quick demo.
- `multi` — a pythonic multi-file layout: a typed `state.py`, one `view` per
  screen under `screens/`, a reusable `Card` `Component` under `components/`, and
  an `app.py` that routes with `Navigator` / `Route` (push/pop + Android back).
- `native` — the `multi` layout plus a screen that calls native capabilities:
  `notify` (fire-and-forget) and `await get_position()` (request/response,
  guarded by `on_device()` + `try/except NativeError`).

```bash
uv run tempest new -t multi          # multi-file project (in the current dir)
```

`tempest dev` cockpit commands: `r` (hot reload, state preserved), `R` (hot
restart, clean state), `s` (raise window), `q` (quit). Saving the file
hot-reloads; a reload incompatible with the live state falls back to a clean
restart.

Apps are **multi-file**: `main.py` may import sibling modules and packages from
your project tree. The simulator (`tempest dev`/`run`) puts the project root on
`sys.path`, and every device path (`deploy`/`serve`/`build`) bundles the **whole
importable tree** (the project root — the nearest ancestor with a
`pyproject.toml` — minus `.venv`, caches, VCS, build output) and puts it on
`sys.path` on the device, so `from my_pkg.foo import bar` resolves identically on
desktop and device.

**Running on your own device — the easy path (no toolchain).** You do **not**
need an Android SDK/NDK or the `android-host` source to test on hardware:

```bash
uv run tempest deploy    # install the bundled host (once) + push the whole project + launch
```

`tempest deploy <app>` ensures the prebuilt host APK (downloaded from the GitHub
release on first use, then cached under `~/.cache/tempestroid`) is installed on
the connected device, pushes the project bundle once
over a short-lived dev server, launches it, and exits. No SDK/NDK, Gradle, or
`android-host` checkout. Repeat runs skip the ~50 MB install (the host is already
there) and just push the new bundle; pass `--force-install` to reinstall the
host. The app keeps running on the device — but it lives in the host, so it is
**not** a standalone artifact you can hand to someone else (use `tempest build`
for that). For a **persistent hot-reload loop** instead, `tempest serve` keeps
the dev server up: editing + saving any file in the tree hot-reloads on device.

```bash
uv run tempest install   # download (cached) + adb-install the prebuilt host APK
uv run tempest serve     # persistent LAN code-push: edit + save → hot reload on device
```

`tempest install` resolves the host APK in order: an explicit `.apk` path/URL →
`TEMPESTROID_HOST_APK` → a bundled asset (only in a source checkout staged with
`make stage-host`) → a download from the matching GitHub release
(`TEMPESTROID_HOST_APK_URL` to override), cached under `~/.cache/tempestroid` so
it's fetched only once. The published wheel does **not** embed the ~100 MB APK
(it would exceed PyPI's per-file limit), so from a PyPI install the download is
the normal path — offline thereafter. With a device connected,
`tempest serve` wires `adb reverse` and launches the host in dev mode pointing at
the dev server. Use `--no-launch` to serve only.

**Shipping a standalone APK — `tempest build apk`.** To produce a self-contained
`.apk` you can give to anyone (it runs the app with **no** dev server), use
`tempest build apk`: it stamps the APK with the project's **own `applicationId`**
so **any number of tempestroid apps install side by side** (never overwriting).
Identity + branding come from **`[tool.tempest]`** in `pyproject.toml`:

```toml
[tool.tempest]
app = "app.py"
id = "com.yourcompany.todolist"   # applicationId; derived (com.example.<project>) if unset
name = "Todo List"                # launcher label; icon / splash / splash_bg / version optional
```

The derived `com.example.*` id is a **placeholder, not publishable** (the Play
Store rejects it) — set your own `id` before publishing and **keep it forever**.
The build runs Gradle but **reuses the prebuilt host natives** (libpython / the
JNI shim / stdlib that ship in the package) and bundles the `android-host`
project **inside the wheel**, so it needs only a **JDK + the Android SDK** — **no
NDK, no CPython toolchain, no `git clone`** (`tempest setup --install` bootstraps
the SDK). Output: `dist/<project>.apk` (debug-signed). `tempest build prd` is the
store-ready release **AAB**; `tempest run` = build + install + launch + logs.

Without a JDK/SDK, `tempest build` falls back to **`--fast`** (repackage the
prebuilt host, no SDK at all) with a warning — that APK keeps the shared
`org.tempestroid.host` id (one app per device). `tempest deploy` covers the same
toolchain-free path for your own connected device.

> **Maintainers:** the host APK (~100 MB — it embeds CPython) is **not** shipped
> inside the PyPI wheel (it would exceed PyPI's per-file limit). `make release`
> builds it (`make apk`) and **attaches it to the GitHub release** as
> `tempest-host-<version>.apk`; `tempest install` / `deploy` download it from
> there (cached). `make publish-host` (re)uploads the asset to an existing
> release; `make stage-host` copies it into a local checkout
> (`tempestroid/_assets/host.apk`, gitignored) so that checkout installs offline.

**Transparent output.** `build`/`run`/`deploy`/`install` announce each step
(`→ … ✓/✗` with elapsed time). `build`/`run` (the from-source APK paths) run a
**preflight** first — checking the host tree, Android SDK, `adb`, and (for `run`)
a connected device — so they fail fast with an actionable hint instead of an
opaque Gradle stack trace; `tempest doctor` runs that same preflight on its own.
Pass `-v`/`--verbose` (on `build`/`run`/`deploy`/`dev`) to echo the raw commands
and stream the full adb/Gradle output; without it, a failed command's tail is
surfaced and the happy path stays quiet.

| Command | Status | Notes |
|---|---|---|
| `tempest new [name]` | ✅ | Scaffold a fully configured project **in the current dir** (id = folder name); pass a `name` only for a new subdirectory. Writes `pyproject.toml` + `app.py` + `.gitignore`. `--template`/`-t`: `default` (single file), `multi` (state + screens/ + components/ + Navigator), `native` (multi + native-capabilities screen) |
| `tempest dev [app]` | ✅ | Simulator + hot reload / hot restart (needs `qt` extra); app from `[tool.tempest]` when omitted; `--device`/`-d` sizes the window to a device preset (e.g. `pixel-7`, `galaxy-s24` — dp, matches Compose); `-v` for tracebacks |
| `tempest deploy [app]` | ✅ | Offline push of the whole project to a device (no SDK/NDK): install the bundled host (if needed) + push bundle + launch; `--force-install`, `-v` |
| `tempest serve [app]` | ✅ | LAN code-push of the whole project + log relay + hot reload; auto `adb reverse` + launch in dev mode (`--no-launch` to skip) |
| `tempest install [src]` | ✅ | Fetch + adb-install the prebuilt host APK (no SDK/NDK); resolves `src`/env/bundled/GitHub-release (cached); `src` = local `.apk`/URL |
| `tempest icon <src>` | ✅ | Generate a square launcher `icon.png` + a centered `splash.png` from one source image (`--out`, `--icon-size`, `--splash-size`, `--splash-scale`). Needs Pillow (`pip install tempestroid[icons]`); feed the output to `tempest build --icon/--splash` |
| `tempest spec` | ✅ | Typed widget/event contract as JSON |
| `tempest doctor` | ✅ | Check the Android build/run prerequisites (JDK, android-host, SDK, adb, device); build readiness sets the exit code, a missing device is informational (only `run`/`install` need one) |
| `tempest setup` | ✅ | Configure the build environment: diagnose JDK/SDK/NDK/build-tools/toolchain; `--install` auto-installs the Android SDK + NDK (`--sdk-dir`, `-v`) |
| `tempest build [apk\|prd]` | ✅ | `apk` (default): a debug, **per-app** APK — its own `applicationId` + launcher label so **any number of tempestroid apps install side by side** (never overwriting). Reuses the prebuilt host natives → needs only **JDK + Android SDK** (no NDK, no CPython toolchain). `prd`: a store-ready release **AAB**. Identity + branding come from **`[tool.tempest]`** (`id`/`name`/`icon`/`splash`/`splash_bg`/`version`) so the command stays short; flags (`--app-id`/`--app-name`/`--icon`/…) override. Advanced: `--fast` (repackage, no SDK, shared id, one app), `--from-source` (stage the CPython toolchain). `-o`, `-v` |
| `tempest run [app]` | ✅ | `build` + install on a device + launch `<app-id>/…MainActivity` + stream logs (needs the toolchain + adb); `--app-id`, `--app-name`, `--app-version`, `--version-code`, `-v` |
| `tempest version` | ✅ | Print the framework version (alias of the global `--version`/`-V`) |
| `tempest clean` | ✅ | Reset the build caches under `~/.tempestroid` (extracted host natives, bundled-host copy, cloned source) — fixes stale-cache build failures after an upgrade; `--keystore` also drops the cached release keystore |
| `tempest lint [path]` | ✅ | `ruff check` on the target (lint only) |
| `tempest fix [path]` | ✅ | `ruff check --fix` + `ruff format` in one pass; `--unsafe` also applies ruff's unsafe autofixes |
| `tempest format [path]` | ✅ | `ruff format` (writes files) |
| `tempest fmt-check [path]` | ✅ | `ruff format --check` (read-only) |
| `tempest type [path]` | ✅ | `pyright` on the target (strict type check) |
| `tempest test [path]` | ✅ | `pytest` (forwards the optional path filter) |
| `tempest check [path]` | ✅ | Full quality gate: lint + fmt-check + type + test (stops at the first failure). Each tool is resolved on `PATH` or via `uv run` |

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
  `letter_spacing`, `line_height`, `max_lines`, `text_overflow`, `aspect_ratio`,
  `flex_wrap` (flow wrapping for a `Wrap` container), and the phase-E9
  typography knobs `text_scale` (a `font_size` multiplier — Qt scales the
  emitted `font-size`, Compose emits `textScale` for `LocalDensity`) and
  `font_asset` (a bundle-relative custom font path — Qt `QFontDatabase`,
  Compose `FontFamily`).
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
- Enums: **`FlexDirection`**, **`FlexWrap`** (`NOWRAP`/`WRAP`/`WRAP_REVERSE`),
  **`JustifyContent`**, **`AlignItems`**,
  **`TextAlign`**, **`FontWeight`**, **`FontStyle`**, **`TextDecoration`**,
  **`TextOverflow`**, **`GradientDirection`**, **`Curve`** (easing —
  `LINEAR`/`EASE_IN`/`EASE_OUT`/`EASE_IN_OUT` plus `EASE`/`BOUNCE`/`ELASTIC`),
  **`StackAlign`** (overlay child alignment in a `Stack`).

### Theme, media query + i18n (phase E9)

Cross-cutting **context** the `view(app)` reads — not nodes in the tree. Changing
any of them swaps an immutable snapshot on the `App` and schedules one coalesced
rebuild (no new patch kind).

- **`Theme`** (`tempestroid.theme`) — frozen: the active **`ThemeMode`**
  (`LIGHT`/`DARK`/`SYSTEM`) plus a small color palette (`primary`/`secondary`/
  `background`/`surface`/`on_primary`/`on_background`/`error`).
  `Theme.is_dark(platform_dark_mode=...)` resolves `SYSTEM` against the OS.
  Swap it with `App.set_theme(theme)`.
- **`MediaQueryData`** (`tempestroid.theme`) — frozen viewport/environment
  snapshot: `width`/`height`/`device_pixel_ratio`/`text_scale_factor`/
  `platform_dark_mode`/`orientation`. The renderer keeps it current via
  `App._update_media(data)` on resize/config-change.
- **`Locale`** (`tempestroid.i18n`) — frozen: `language` (BCP-47) + optional
  `region` + `rtl` (layout direction). Swap it with `App.set_locale(locale)`.
  When the renderer is told a node is RTL, both `Style` translators mirror the
  box model's start/end (padding/margin left↔right) and flip `text_align`.
- **`translate(key, locale, translations, **kwargs)`** / alias **`t`**
  (`tempestroid.i18n`) — a dependency-free table lookup with `str.format`
  interpolation; a missing key/language degrades to the key itself.

### Widgets (`tempestroid.widgets`)

The declarative IR — bare-noun widgets.

- **`Widget`** (base) — every node carries `key` / `style` plus the phase-E9
  accessibility fields `semantics` (**`Semantics`**: `label`/`role`/`hint`,
  propagated to both renderers and `introspect()`), `focusable`, and
  `focus_order`. **`Text`**, **`Button`**, **`Column`**, **`Row`**,
  **`Container`**, **`ScrollView`** (scrollable container), **`SafeArea`**
  (insets its child past the status/navigation bars + notch; `edges` selects
  which sides, default all — `SafeAreaEdge` enum).
- **`Stack`** — overlay/z-order container: children share one box, layered in
  declaration order. A child with `position=ABSOLUTE` is anchored by its
  `top`/`right`/`bottom`/`left` insets; the rest align by `Style.stack_align`
  (`StackAlign` enum). The framework's overlay primitive (scrim, modal, FAB).
- Refined layout (phase E6) — **`Wrap`** (a flow container whose children wrap to
  the next line when the row fills, driven by `Style.flex_wrap`; Compose
  `FlowRow`/`FlowColumn`, Qt custom flow layout), **`PageView`** (a paginated
  horizontal carousel: `children` are pages, the active `page` lives in app state
  and `on_page_change` (**`PageChangeHandler`**) → **`PageChangeEvent`** updates
  it; Compose `HorizontalPager`, Qt `QStackedWidget` + prev/next) and
  **`AspectRatio`** (a single-child box fixing the `ratio` = width / height;
  Compose `Modifier.aspectRatio`, Qt derives the missing dimension).
- Platform layout (phase E8) — **`KeyboardAvoidingView`** (a vertical container
  that insets its `children` when the on-screen keyboard appears; Compose
  `Modifier.imePadding()` via `WindowInsets.ime`, Qt listens on
  `QApplication.inputMethod().keyboardRectangleChanged` and behaves like a
  `Column` on the desktop). Declares no event contract.
- **`GestureDetector`** — wraps a `child` and reports pointer gestures via
  **`TapHandler`** / **`LongPressHandler`** / **`SwipeHandler`** props
  (`on_tap` / `on_double_tap` / `on_long_press` / `on_swipe`).
- Advanced gestures (phase E4) — specialized single-purpose wrappers, each
  lowering to the same renderer-agnostic contract (Qt via mouse/`QGraphicsView`/
  `QDrag`, Compose via `pointerInput`/`SwipeToDismissBox`/`graphicsLayer`):
  **`PanHandler`** (`on_pan` → **`PanEvent`**: delta + fling velocity),
  **`ScaleHandler`** (`on_scale` → **`ScaleEvent`**: pinch scale/focus/rotation,
  plus `on_double_tap`), **`DoubleTapHandler`** (`on_double_tap` → `TapEvent`),
  **`Draggable`** (`drag_data` + `on_drag` → **`DragEvent`**) paired with
  **`DragTarget`** (`on_drop` → `DragEvent`) — both via the **`DragHandler`**
  alias, **`Dismissible`** (swipe-to-delete: `direction` + `on_dismiss` →
  `DismissEvent`), **`ReorderableList`** (drag to reorder: `children` +
  `on_reorder` (**`ReorderHandler`**) → **`ReorderEvent`**; the handler mutates a
  keyed list so the A2 diff emits a `Reorder`) and **`InteractiveViewer`** (pan +
  zoom: `min_scale`/`max_scale` + `on_interaction` → `ScaleEvent`).
- Animation widgets (phase E3) — the interpolation runs in the **core**
  (`AnimationController` advances a 0..1 value on the app's frame clock, `Tween`
  interpolates a `float`/`Color`/`Edge`, the `view` folds the result into a
  `Style`), so both renderers receive only the final per-frame props.
  **`Animated`** (wraps a `child` rebuilt with interpolated style each frame),
  **`AnimatedList`** (a `Column`/`Row` whose items fade + expand in on insert and
  collapse out on remove — `enter_duration_ms`/`exit_duration_ms`/curves),
  **`Hero`** (a `hero_tag` shared-element transition across `Navigator` screens),
  **`Shimmer`** (sweeps a gradient highlight over a `child` as a loading
  placeholder) and **`Skeleton`** (the childless rectangular shimmer). Qt
  interpolates in the core and drives `QPropertyAnimation`/`QTimer`; Compose can
  use its native animation engine (a documented conformance divergence).
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
- Value-bearing inputs: **`Input`** (text — with `secure` password masking + a
  modern eye / eye-off reveal toggle, regex `pattern`, `keyboard` type,
  `max_length`, and `leading_icon`/`trailing_icon` shown inside the field),
  **`TextArea`** (multi-line), **`Checkbox`** (boolean), **`Switch`** (boolean toggle),
  **`Slider`** (numeric range), **`DatePicker`** (ISO date), **`FilePicker`**
  (file selection).
- Selection + segmented inputs (phase E5): **`Dropdown`** (single-choice select —
  `options` + `value`, emits **`SelectEvent`** with the option `value` + `index`),
  **`TimePicker`** (`"HH:MM"` value, emits **`TimeChangeEvent`**), **`RangeSlider`**
  (dual-handle `low`/`high` over `[min_value, max_value]`, emits
  **`RangeChangeEvent`**), **`Autocomplete`** (text + filtered suggestions; emits
  **`TextChangeEvent`** while typing and **`SelectEvent`** on pick), **`PinInput`**
  (segmented PIN/OTP of `length` cells; emits **`TextChangeEvent`** per edit and a
  **`SubmitEvent`** once full) and **`MaskedInput`** (input `mask` — `'9'` digit,
  `'A'` letter, else literal — emits **`TextChangeEvent`**).
- Forms (phase E5, `tempestroid.widgets.forms`): **`Form`** (a container of
  **`FormField`**s, `on_submit` → **`SubmitEvent`**) and **`FormField`** (a
  labelled wrapper around a `child` input, carrying typed **`Validator`** rules,
  `name`, `error`, `on_validate` → **`ValidationEvent`**). A **`Validator`** is a
  `Callable[[Any], str | None]` (an error string or `None`). `Form.validate(values)`
  runs every field's validators **purely in Python** — the same boundary-validation
  philosophy as `parse_event` — and returns a **`FormState`** (a frozen
  `{"errors": dict[str, str], "valid": bool}` that serializes to plain JSON, with no
  nested models), so a renderer receives an already-validated tree with each
  field's `error` filled in; the app gates `SubmitEvent` on `FormState.valid`. Both
  `Form.fields` and `FormField.child` cross the bridge as child nodes (never as
  props); validators are pure Python and are never serialized.
- Presentation widgets: **`Image`** (URL/asset, `fit`), **`Icon`** (named glyph —
  resolves a built-in [`Icons`](#icons-tempestroidicons) name to a vector glyph,
  else falls back to the platform set), **`ProgressBar`**
  (determinate/indeterminate), **`Spinner`** (activity).
- Media + graphics widgets (phase E7): **`Canvas`** — a retained-mode drawing
  surface taking a `commands` list of serializable draw commands
  (**`MoveTo`** / **`LineTo`** / **`ArcTo`** / **`Close`** / **`FillCmd`** /
  **`StrokeCmd`** / **`DrawText`** / **`DrawRect`** / **`DrawOval`**, the
  discriminated **`DrawCommand`** union; colors are `[r, g, b, a]` float lists, so
  the list lowers to pure JSON and diffs by value); **`VideoPlayer`** (`src` +
  `autoplay`/`loop`/`controls`/`muted`), **`WebView`** (`url` +
  `javascript_enabled`), **`Svg`** (`src` + `fit`), **`CameraPreview`**
  (`facing`), **`QrScanner`** (`on_scan` → **`QrScanEvent`**), **`MapView`**
  (`latitude`/`longitude`/`zoom` + JSON `markers`), and the effect wrappers
  **`Blur`** / **`BackdropFilter`** (`radius` + `child`) and **`ClipPath`**
  (**`ClipShape`** `shape` + `radius` + `child`). `CameraPreview`/`QrScanner`/
  `MapView` are device-only — the Qt simulator shows an explicit placeholder.
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
  **`ImageFit`** (contain/cover/fill/none), **`ClipShape`**
  (circle/rounded_rect/oval).
- **`EventHandler`** — the typed handler-prop wrapper used by every handler field
  (`on_click`, `on_change`, `on_select`); sync or `async`, zero- or one-argument.

### Icons (`tempestroid.icons`)

A curated, DIY (dependency-free) set of common line icons — Lucide-style vector
glyphs both renderers draw identically by stroking one 24×24 SVG path. Pass a
name to `Icon(name=…)` or to an input's `leading_icon`/`trailing_icon`.

- **`Icons`** — a `StrEnum` of the curated names (`Icons.EYE`, `Icons.LOCK`,
  `Icons.SEARCH`, … `Icons.EYE == "eye"`), so you get autocomplete and may also
  pass the raw string.
- **`ICON_PATHS`** — `dict[str, str]` mapping each name to its SVG path `d` data.
- **`icon_path(name)`** — resolve an `Icons` member or raw string (curated or
  custom) to its `d` string, or `None` when unknown (renderers fall back to the
  platform set / the raw name).
- **`icon_names()`** — the sorted list of available names (curated + custom).
- **`svg_to_path(source)`** — convert an SVG image (a file path or raw markup) to
  one normalized `d` string, flattening `path`/`circle`/`line`/`rect`/`polyline`/
  `polygon` shapes — so a project SVG becomes a tempestroid icon.
- **`register_icon(name, source=…)` / `register_icon(name, path=…)`** — register
  a custom icon (from an SVG file/markup, or a ready `d`) under a name, so
  `Icon(name=…)`, an input's `leading_icon`/`trailing_icon` and `icon_path` all
  resolve it like a built-in.

Input icon slots are typed **`Icons | str | None`**: pass an `Icons` member for
autocomplete on the curated set, or any string for a registered custom / platform
icon.

### Components (`tempestroid.components`)

Higher-level, reusable building blocks — each a **`Component`** that lowers to
primitive widgets, so they work in both renderers (Qt and Compose) with zero
renderer changes and are fully device-ready. Every component takes an optional
`style` that is merged over its default via **`merge_style`**.

- **`AppBar`** — top bar: optional `leading` widget, `title`, trailing `actions`.
- **`CollapsingAppBar`** — a sliver-style header that shrinks as the content
  scrolls: the app feeds the current `scroll_offset` (from a list's `on_scroll`)
  and the component eases its height from `expanded_height` down to
  `collapsed_height`, diffing the derived height as an ordinary prop (no new IR).
- **`Header`** / **`Footer`** — page header band (title + optional subtitle) and
  a centered bottom bar holding arbitrary `children`.
- **`Table`** — a static data table built from typed **`TableRow`** /
  **`TableCell`** values plus optional `headers`; **`DataTable`** — a string-matrix
  convenience (`columns` + `rows`, optional `sortable` header glyph). Both lower
  to a `Column` of `Row`s of cells, so they render in both renderers unchanged.
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
- Advanced-gesture events (phase E4): **`PanEvent`** (`dx`/`dy` delta +
  `vx`/`vy` fling velocity), **`ScaleEvent`** (`scale` + `focus_x`/`focus_y`
  focal point + `rotation`), **`DragEvent`** (`data` opaque label + optional
  `x`/`y` drop position) and **`ReorderEvent`** (`from_index` → `to_index`).
  `Dismissible` reuses **`DismissEvent`**.
- **`RouteChangeEvent`** (`name` + typed `params`) — emitted when navigation
  settles on a new route.
- Virtualized-list events: **`ScrollEvent`** (`offset` + `direction`),
  **`RefreshEvent`** (pull-to-refresh) and **`EndReachedEvent`** (threshold
  reached) — emitted by `LazyColumn` / `LazyRow` / `LazyGrid` / `SectionList` /
  `RefreshControl`.
- Overlay events: **`DismissEvent`** (optional `overlay_id`) — an overlay
  dismissed by a host-owned gesture (`Dialog` / `BottomSheet` / `Popover`); and
  **`MenuSelectEvent`** (`value` + `label`) — a `Menu` / `ActionSheet` selection.
- Input + form events (phase E5): **`SelectEvent`** (`value` + 0-based `index`),
  **`TimeChangeEvent`** (`"HH:MM"` `value`), **`RangeChangeEvent`** (`low` + `high`
  floats), **`SubmitEvent`** (flat `values: dict[str, str]`) and
  **`ValidationEvent`** (`field` + `value` + optional `error`). The matching
  handler aliases are **`SelectHandler`** / **`TimeChangeHandler`** /
  **`RangeChangeHandler`** / **`SubmitHandler`** / **`ValidationHandler`**.
- Layout event (phase E6): **`PageChangeEvent`** (`page` + `previous`) — emitted
  by a `PageView` when the active page changes (handler alias
  **`PageChangeHandler`**).
- Media event (phase E7): **`QrScanEvent`** (`data` + `format`) — emitted by a
  `QrScanner` for each decoded QR/barcode (handler prop `on_scan`).
- Platform/system events (phase E8) — streamed from the host over reserved event
  tokens (no widget handler): **`LifecycleEvent`** (`state`, the **`AppState`**
  enum foreground/background/inactive), **`SensorEvent`** (`sensor` — the
  **`SensorType`** enum — + `values` + `timestamp_ms`), **`ConnectivityEvent`**
  (`state`, the **`ConnectivityState`** enum connected/disconnected/wifi/mobile)
  and **`DeepLinkEvent`** (`url` + parsed `params`).
- Context events (phase E9) — streamed from the host over reserved tokens (no
  widget handler): **`ThemeChangeEvent`** (`mode`, the **`ThemeMode`** enum) over
  `THEME_TOKEN` → `App.set_theme`, and **`LocaleChangeEvent`** (`language` +
  optional `region` + `rtl`) over `LOCALE_TOKEN` → `App.set_locale`.
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

### Animation (`tempestroid.animation`)

The interpolation runs in the **core**, so both renderers only ever see final
per-frame props (the divergence — Qt interpolates in the core, Compose may drive
its native engine — is pinned by the conformance suite).

- **`AnimationController`** — drives a normalized `value` (0.0..1.0) on the app's
  frame clock: `forward()` ramps toward 1.0, `reverse()` toward 0.0, `stop()`
  halts and unregisters. Constructed with `duration_s` + `curve`, or a
  `Spring` for physics-based motion. Injectable `time_source` for deterministic
  tests.
- **`Tween[T]`** — a frozen linear interpolator (`begin` → `end`); `at(t)`
  interpolates `float`, `Color` (per channel), `Edge` (per side) or a numeric
  `tuple`. The `view` reads `at(controller.value)` to feed an interpolated
  `Style`.
- **`Spring`** — frozen spring parameters (`stiffness`/`damping`/`mass`) for an
  `AnimationController` instead of a fixed duration.
- `App` owns the frame clock: **`register_animation(ctrl)`** starts a coalesced
  `loop.call_later(1/60)` tick that advances every active controller and requests
  a rebuild; the clock stops re-arming once no controller remains. The reserved
  `__frame__` device token routes to `App._tick_from_device()` (one advance per
  host frame). `App.__init__` accepts an optional `time_source` kwarg.

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
- **`resolve_device(name)`** — resolve a forgiving name (`"pixel-7"`, `"PIXEL_7"`,
  `"Google Pixel 7"`) to a `Device`, or `None`. Backs `tempest dev --device`.

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
  round-trip, and **`has_animations`** (`app.has_animations`), so the host can
  start/stop its `withFrameNanos` frame loop without a round-trip.
- **`BACK_TOKEN`** (`"__back__"`) — the reserved event token the host sends on a
  system back action (e.g. the Android back gesture). The bridge routes it
  straight to `App.pop` (no widget handler, no new JNI entry) — it pops a screen,
  or is a no-op at the root where the host's default close-the-app action runs.
- **`FRAME_TOKEN`** (`"__frame__"`) — the reserved event token the host sends
  once per frame from its `withFrameNanos` loop while `has_animations` is `True`.
  The bridge routes it straight to `App._tick_from_device`, which advances every
  active `AnimationController` one frame and re-renders (no widget handler, no new
  JNI entry). The Qt simulator drives its own clock and never emits this token.
- **`DISMISS_TOKEN_PREFIX`** (`"__dismiss__"`) — the reserved event-token prefix
  the host sends when an overlay is dismissed by a host-owned gesture (scrim tap,
  swipe-down): `"__dismiss__:<overlay_id>"`. The bridge strips the prefix and
  routes the id to `App.dismiss` (no widget handler, no new JNI entry).
- **`SENSOR_TOKEN_PREFIX`** (`"__sensor__"`) / **`LIFECYCLE_TOKEN`**
  (`"__lifecycle__"`) / **`CONNECTIVITY_TOKEN_PREFIX`** (`"__connectivity__"`)
  (phase E8) — reserved tokens carrying *continuous* host streams over the same
  event channel: `"__sensor__:<type>"` → `dispatch_sensor_event`,
  `"__lifecycle__"` → `dispatch_lifecycle_event`,
  `"__connectivity__:<state>"` → `dispatch_connectivity_event`. Each rides the
  existing transport (no new JNI/C entry) and is routed in **both**
  `bridge/jni.py` and `devserver/client.py` (so code-push gets them too).
- **`THEME_TOKEN`** (`"__theme__"`) / **`LOCALE_TOKEN`** (`"__locale__"`)
  (phase E9) — reserved bare tokens carrying a host-driven context change over
  the same event channel: `"__theme__"` (payload `{"mode": "dark"}`, validated as
  a `ThemeChangeEvent`) → `App.set_theme`, and `"__locale__"` (payload
  `{"language": "ar", "rtl": true}`, validated as a `LocaleChangeEvent`) →
  `App.set_locale`. Both ride the existing transport (no new JNI/C entry).
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
**`on_device()`** reports whether the native host is present, so a module can
emulate (prefs/SQLite) or stub (`device_only`) on the desktop.

#### Platform + system (phase E8)

A wider platform surface, same two shapes (plus the sensor/lifecycle/connectivity
*streams* over the reserved tokens above). Capabilities with no desktop hardware
stub on the Qt simulator with an explicit `device_only` `NativeError`; the ones
that can be emulated run for real off-device.

- **Haptics** (fire-and-forget): **`vibrate(duration_ms=50)`**,
  **`impact(style=ImpactStyle.MEDIUM)`** (the **`ImpactStyle`** enum
  light/medium/heavy).
- **System** (set = fire-and-forget, get = `async`):
  **`set_status_bar(*, hidden=None, color=None, style=None)`** (**`StatusBarStyle`**
  enum), **`await get_brightness() -> float`**, **`set_brightness(value)`**,
  **`keep_awake(enabled)`**, **`set_orientation(orientation)`** (the
  **`Orientation`** enum portrait/landscape/auto).
- **Sensors** (stream): **`start_sensor(sensor, callback, rate_ms=100) ->
  Callable[[], None]`** registers a `SensorEvent` callback (the **`SensorCallback`**
  alias; returns a `stop` handle) and **`stop_sensor(sensor)`**.
- **Lifecycle** (stream): **`on_app_state_change(callback) -> Callable[[], None]`**
  registers a `LifecycleEvent` callback (the **`LifecycleCallback`** alias; returns
  an `unregister`); driven for real on the Qt simulator by
  `QApplication.applicationStateChanged`.
- **Connectivity**: **`await get_connectivity() -> ConnectivityState`** and the
  stream **`on_connectivity_change(callback) -> Callable[[], None]`** (the
  **`ConnectivityCallback`** alias).
- **Permissions** (`async`): **`await request_permission(permission)`** /
  **`await check_permission(permission)`** → **`PermissionResult`**
  (`permission` + **`PermissionStatus`** granted/denied/permanently_denied; the Qt
  simulator returns granted — the desktop has every capability).
- **Biometrics** (`async`): **`await authenticate(reason="") -> BiometricResult`**
  (`authenticated` + optional `error`); Qt raises `device_only`.
- **Secure storage**: **`await get_secret(key)`** / **`set_secret(key, value)`** /
  **`delete_secret(key)`** (Android Keystore-backed; Qt raises `device_only` — no
  silent plaintext fallback).
- **Preferences** (real on the desktop — a JSON file under
  `~/.tempestroid/prefs.json`): **`await get_pref(key, default=None)`** /
  **`set_pref(key, value)`** / **`delete_pref(key)`** /
  **`await get_all_prefs() -> dict[str, Any]`**.
- **Database** (real on the desktop — `sqlite3` under `~/.tempestroid/app.db`):
  **`await execute(sql, params=()) -> QueryResult`** (`columns` + `rows`) /
  **`await execute_many(sql, params_list)`**.
- **Push** (FCM): **`await register_push() -> PushToken`** (Qt raises
  `device_only`; the device path needs `google-services.json` — drop it into
  `android-host/app/` and the build enables FCM) and
  **`schedule_notification(title, body, delay_s)`** (local notification).
- **Background tasks** (WorkManager): **`schedule_task(name, *, interval_s=None)`**
  (one-shot when `interval_s` is `None`, else periodic ≥15 min) /
  **`cancel_task(name)`**, with **`on_background_task(name, callback)`** to run a
  handler when the task fires — the worker re-enters Python (the live interpreter
  if the app is up, else a fresh short-lived one).

Example: [`examples/platform/app.py`](examples/platform/app.py) exercises haptics
(with the Qt fallback), preferences (real JSON store on the desktop), the
lifecycle stream and a `KeyboardAvoidingView`-wrapped input. The Python half is
fully unit-tested off-device (envelopes, typed results, stream-callback
registries, the real prefs/SQLite emulation via `tmp_path`); biometrics, FCM,
WorkManager and real sensors are hardware-gated and validated on a device.

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
| E0 | Navigation + routes (push/pop, tabs, drawer, back button, deep link) | ✅ |
| E1 | Virtualized lists + scroll (lazy, sticky section, pull-to-refresh, infinite) | ✅ |
| E2 | Overlays + feedback (dialog, bottom sheet, toast, tooltip, menu/popover, action sheet) | ✅ |
| E3 | Animation framework (`AnimationController`/`Tween`/`Spring`, `Animated`/`AnimatedList`/`Hero`/`Shimmer`/`Skeleton`) | ✅ |
| E4 | Advanced gestures (`PanHandler`/`ScaleHandler`/`Draggable`/`DragTarget`/`Dismissible`/`ReorderableList`/`InteractiveViewer`) | ✅ |
| E5 | Inputs + forms (`Dropdown`/`TimePicker`/`RangeSlider`/`Autocomplete`/`PinInput`/`MaskedInput`, `Form`/`FormField`/`Validator`/`FormState`) | ✅ |
| E6 | Refined layout (`flex_wrap`/`Wrap`/`PageView`/`AspectRatio`/`CollapsingAppBar`/`Table`/`DataTable`, `PageChangeEvent`) | ✅ |
| E7 | Media + graphics (`Canvas`/`Svg`/`VideoPlayer`/`WebView`/`Blur`/`ClipPath`/`CameraPreview`/`QrScanner`/`MapView`) | ✅ |
| E8 | Platform + system (haptics/sensors/system/lifecycle/permissions/biometrics/secure_storage/prefs/database/connectivity/push/background, `KeyboardAvoidingView`, `LifecycleEvent`/`SensorEvent`/`ConnectivityEvent`/`DeepLinkEvent`) | ✅ |
| E9 | Cross-cutting: theme/dark mode (`Theme`/`ThemeMode`) + `MediaQueryData` + i18n/RTL (`Locale`/`translate`) + accessibility (`Semantics`/`focusable`) + custom fonts (`text_scale`/`font_asset`), `ThemeChangeEvent`/`LocaleChangeEvent` over `THEME_TOKEN`/`LOCALE_TOKEN` | ✅ |

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
