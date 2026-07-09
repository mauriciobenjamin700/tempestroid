# CLI (`tempest`)

The `tempest` CLI is the framework's single cockpit: it scaffolds the project,
runs it in the simulator with hot reload, pushes to a device, builds the APK, and
even wraps lint/type/test. This guide is the **complete reference** — every
command with what it does, when to use it, and a copy-paste example.

Start by discovering everything that exists:

```bash
tempest --help            # list the commands, grouped by purpose
tempest <command> --help  # options and arguments for one command
```

!!! tip "The `uv run` prefix"
    Inside a `uv`-managed project, run `uv run tempest …` (uses the project's
    environment). If `tempest` is already on PATH (active venv / global install),
    the `uv run` prefix is optional. The examples below omit it for brevity.

## Quick map

The commands fall into four groups — the same grouping `tempest --help` shows:

| Group | Command | Does |
|---|---|---|
| **Create & develop** | [`new`](#new) | Scaffold a tempestroid app in the current folder. |
| | [`dev`](#dev) | Qt simulator with hot reload. |
| | [`serve`](#serve) | LAN code-push to a device (no rebuild). |
| **Ship & install** | [`deploy`](#deploy) | Run the app on a device **offline** (no SDK/NDK). |
| | [`install`](#install) | adb-install the prebuilt host. |
| | [`build`](#build) | Build the shippable APK/AAB (own id). |
| | [`run`](#run) | `build` + install on device + logs. |
| | [`icon`](#icon) | Generate icon + splash from one image. |
| | [`optimize`](#optimize) | Quantize/convert an ONNX model for the device. |
| **Diagnose & inspect** | [`doctor`](#doctor) | Check the Android build prerequisites. |
| | [`setup`](#setup) | Install/configure the SDK + NDK. |
| | [`spec`](#spec) | Print the typed contract (widgets/events) as JSON. |
| | [`clean`](#clean) | Reset the build caches under `~/.tempestroid`. |
| | [`version`](#version) | Show the framework version. |
| **Quality** | [`check`](#check) | Full gate: lint + fmt-check + type + test. |
| | [`lint`](#lint) / [`fix`](#fix) | `ruff check` (read-only) / autofix + format. |
| | [`format`](#format) / [`fmt-check`](#fmt-check) | `ruff format` (write / check-only). |
| | [`type`](#type) | strict `pyright`. |
| | [`test`](#test) / [`uitest`](#uitest) | `pytest` / native UI test. |

## Typical flow

```bash
tempest new                 # scaffold in the current folder (id = folder name)
tempest dev                 # simulator + hot reload (edit and save → reloads)
tempest deploy              # run on a connected device, offline (no SDK/NDK)
tempest build apk           # shippable APK with its own id (JDK + SDK)
tempest run                 # build + install + logs on the device
```

!!! info "`dev`/`serve` read `[tool.tempest] app`"
    Run them with no argument inside the project — the app path comes from
    `pyproject.toml`. Pass a path to override (e.g.
    `tempest dev examples/counter/app.py`).

---

## Create & develop

### `new`

Scaffold a runnable tempestroid app **in the current folder** (the
`applicationId` derives from the folder name). Pass a name to create a subfolder.

```bash
tempest new                 # scaffold here
tempest new my-app          # creates ./my-app/
```

### `dev`

Boots the **Qt simulator** with hot reload: edit and save, the UI reloads while
preserving state. This is the day-to-day dev loop (needs the `qt` extra).

```bash
tempest dev                             # reads [tool.tempest] app
tempest dev -d pixel-7                  # size the window to a device preset
```

- `--device` / `-d` — device preset (`pixel-7`, `galaxy-s24`, …) to size the
  window to a real viewport.

See the [`tempest dev` cockpit](#the-tempest-dev-cockpit) for the interactive
keys.

### `serve`

**LAN code-push**: pushes the project's code to the host already installed on the
device and hot-reloads **without rebuilding the APK**. Ideal for iterating on real
hardware after the first `install`.

```bash
tempest install             # once: install the host on the device
tempest serve               # push + hot reload over LAN
```

- `--port` (default 8765), `--host` (default `0.0.0.0`), `--no-launch`.

---

## Ship & install

Two paths to the device: **offline** (`deploy`/`serve`/`install`, no SDK/NDK) and
**shippable APK** (`build`/`run`, needs JDK + SDK). See
[Build, deploy & publish](build.md) for the choice.

### `deploy`

Runs the whole app on a connected device **offline** — installs the bundled host,
pushes the project, and launches. Zero Android toolchain.

```bash
tempest deploy              # no SDK/NDK
```

### `install`

adb-installs the **prebuilt host** (the host APK ships in the package — offline,
instant). Then use `serve` to push apps.

```bash
tempest install                     # bundled host (offline)
tempest install ./my-host.apk       # from a local .apk
tempest install --no-launch         # install only
```

### `build`

Builds the **shippable** artifact with the whole project baked in and its own
`applicationId` (installs side by side with other apps). Reads `[tool.tempest]`
from `pyproject.toml`.

```bash
tempest build apk               # per-app debug APK (JDK + SDK, no NDK)
tempest build release-apk       # signed release APK (outside the Play Store)
tempest build prd               # release AAB for the store
```

- `--feature <cap>` (repeatable) — bundle a heavy optional capability:
  `vision`, `camera`, `qr`, `push`, `video`, `maps`. Each opt-in needs a
  **from-source** build (SDK + NDK).
- `--from-source` — stage the full CPython toolchain instead of reusing the
  prebuilt natives.
- `--app-id`, `--app-name`, `--app-version`, `--icon`, `--splash`, `--keystore`,
  `--output`.

!!! tip "Vision app (on-device ONNX)"
    An app that uses `ort_vision_sdk`/`onnxruntime` needs the vision stack baked
    in — build it like this:
    ```bash
    tempest setup --install                              # SDK + NDK
    tempest build apk --feature vision --from-source     # the CLI fetches CPython itself
    ```
    Without `--feature vision`, the app opens to a **blank** home (the vision
    libs are not in the lean APK). Since 0.15.4 the CLI fetches the Android
    CPython prefix automatically — no manual staging.

### `run`

`build apk` + install on the device + stream logs. The shortcut to see the real
APK running.

```bash
tempest run
```

### `icon`

Generates `icon.png` (launcher icon) + `splash.png` (boot splash) from a single
source image (uses Pillow).

```bash
tempest icon logo.png
```

### `optimize`

Optimizes an **ONNX model** for on-device use: quantizes (INT8/fp16) then converts
to the ORT mobile format, shrinking the model the app ships. Runs on the host, at
build time (needs the vision extra).

```bash
tempest optimize model.onnx                 # INT8 + .ort (default)
tempest optimize model.onnx -q fp16         # fp16 instead of int8
tempest optimize model.onnx --no-ort        # keep .onnx, skip conversion
```

- `--quantize` / `-q` — `int8` (default, ~4× smaller), `fp16`, or `none`.
- `--no-ort` — skip the mobile-format conversion.
- `--out` — output directory (default: next to the model).

---

## Diagnose & inspect

### `doctor`

Checks the **Android build/run prerequisites** (JDK, android-host, SDK, adb,
device) and prints what's missing. Build readiness sets the exit code; a missing
device is informational only (only `run`/`install` need one).

```bash
tempest doctor
```

### `setup`

Configures the build environment. Without a flag it diagnoses what's missing;
with `--install` it **installs the Android SDK + NDK** into a managed directory
(needs a JDK).

```bash
tempest setup                       # diagnosis + plan
tempest setup --install             # install SDK + NDK
```

### `spec`

Prints the framework's **typed contract** (widgets + events) as JSON — useful for
tooling, code generation, and tests.

```bash
tempest spec > contract.json
```

### `clean`

Resets the build caches under `~/.tempestroid` (extracted host natives, host
copy, source clone). Fixes stale-cache failures after an upgrade.

```bash
tempest clean                       # clear caches
tempest clean --keystore            # also delete the release keystore
```

### `version`

Shows the framework version (same as `tempest --version`).

```bash
tempest version
```

---

## Quality

Thin wrappers over `ruff` / `pyright` / `pytest`, to run the same gate locally and
in CI. All take an optional path (default: the project).

### `check`

The **full gate**: `lint` + `fmt-check` + `type` + `test`, in sequence. Run it
before committing.

```bash
tempest check
```

### `lint`

`ruff check` on the target — reports only, no changes.

```bash
tempest lint
```

### `fix`

Applies **every ruff autofix + format** in one pass.

```bash
tempest fix
tempest fix --unsafe        # include fixes marked unsafe
```

### `format`

`ruff format` — writes the files.

```bash
tempest format
```

### `fmt-check`

`ruff format --check` — read-only (fails if something is unformatted).

```bash
tempest fmt-check
```

### `type`

`pyright` on the target (strict type check).

```bash
tempest type
```

### `test`

`pytest`, forwarding the optional path filter.

```bash
tempest test
tempest test tests/unit/test_state.py
```

### `uitest`

Runs a Playwright-style **native UI test** file (F9 driver): locate nodes by
key/text/semantics, act with tap/fill, and assert with `expect_*`, with auto-wait
(no fixed sleeps).

```bash
tempest uitest test_home.py                  # headless (in-process, no renderer)
tempest uitest test_home.py -t emulator      # REAL Compose render on an emulator
tempest uitest test_home.py -t emulator -j 4 # 4 isolated instances in parallel
```

- `--target` / `-t` — `headless` (renderer-agnostic) or `emulator` (real Compose
  render, one screenshot per test).
- `-j N` — shard across N instances; `--isolate-adb` gives each a private adb
  server.

The file is an app module (`view` + `make_state`) plus `async def test_*(page)`
functions.

## The `tempest dev` cockpit

Interactive keys while the simulator runs:

| Key | Action |
|---|---|
| `r` | Hot reload (state preserved). |
| `R` | Hot restart (clean state). |
| `s` | Raise the window. |
| `q` | Quit. |

Saving the file triggers hot reload automatically; if the reload is incompatible
with the live state, the loop falls back to a clean restart. A bad save is caught
and printed — the loop survives.

!!! note "build / run need JDK + Android SDK"
    `tempest build`/`run` run Gradle reusing the prebuilt natives (the
    `android-host` ships in the package), so they need **JDK + Android SDK** —
    **no NDK, no CPython toolchain, no `git clone`** (except opt-in features via
    `--feature`, which need `--from-source` + NDK). To run on the device
    **without an SDK**, use `tempest deploy`/`serve`. See
    [Build, deploy & publish](build.md), the [installation](../instalacao.md),
    and the [runtime research](../research/android-runtime.md).

## The app-file contract

For `tempest dev`/`serve`, the module must expose:

- `make_state() -> S` — the initial-state factory (called on every hot restart).
- `view(app) -> Widget` — the UI builder.

The loader compiles/executes the file fresh on every load (no `.pyc` reuse), so
reloads always see the latest edit. Keep the module free of module-level Qt
imports (use `if __name__ == "__main__"`) so the same file runs on the desktop and
on the device.
