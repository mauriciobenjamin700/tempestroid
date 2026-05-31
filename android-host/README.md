# android-host/ — Kotlin host embedding official CPython + Compose renderer

A minimal Gradle/Kotlin Android app that embeds **official CPython 3.14**
(PEP 738), boots it on a **background thread**, and renders the tempestroid
widget tree with **Jetpack Compose**. Modelled on the CPython
`Platforms/Android/testbed`: it loads `libpython` via a hand-rolled JNI shim and
drives it with the embedding C-API (`PyConfig` / `Py_InitializeFromConfig` /
`Py_RunMain`) — **no pyjnius, Chaquopy, or python-for-android**.

> **Validated on a real arm64 device** (Xiaomi `23053RN02A`, Android 15, on
> 2026-05-30): the APK boots CPython 3.14 off the UI thread, mounts a styled
> counter, and a real button tap drives `count 0→N` through the bridge. Needs an
> Android SDK + NDK and the artifacts from [`../toolchain`](../toolchain)
> (CPython prefix + wheels) staged into `app/src/main/` — **not buildable in a
> bare WSL session without the toolchain**.

## What's here (phases B2–B4, all done)

```text
android-host/
├── settings.gradle.kts
├── build.gradle.kts                 # root (plugin versions)
├── gradle.properties
├── gradle/wrapper/                  # Gradle wrapper 8.11.1 (see gotchas)
└── app/
    ├── build.gradle.kts             # assets/jniLibs wiring, CMake, .gz rename, ignoreAssetsPattern override
    └── src/main/
        ├── AndroidManifest.xml      # extractNativeLibs=false (so + page-aligned)
        ├── java/org/tempestroid/host/
        │   ├── MainActivity.kt      # extract assets, boot Python off-UI-thread, setContent + bridge→tree sink
        │   ├── PythonRuntime.kt     # JNI surface: startPython / dispatchEvent / onMessageFromPython + messageSink
        │   ├── TempestTree.kt       # device-side IR holder: parse mount + apply patches as Compose snapshot state
        │   └── TempestRenderer.kt   # RenderNode(): TempestNode → Compose; style spec → Modifier/Arrangement/Alignment
        └── c/
            ├── CMakeLists.txt       # links libpython3.14
            └── tempest_host.c       # PyConfig + Py_InitializeFromConfig + Py_RunMain
                                      #   + built-in _tempest_host module (send_to_host / set_event_sink)
                                      #   + dispatchEvent JNI entry (Kotlin → Python)
```

## How it runs (B2 → B3 → B4)

```text
            Python thread (asyncio)                    UI thread (Compose)
            ───────────────────────                    ───────────────────
 run_device(state, view)
   App builds the tree, diffs → patches
   JniBridge.serialize → _tempest_host.send_to_host(json)
                       └──────────► PythonRuntime.onMessageFromPython(json)
                                      messageSink → runOnUiThread { tree.apply(json) }
                                                      TempestTree: mount → root node
                                                                   patch → mutate snapshot state
                                                      RenderNode(root) recomposes ◄── Compose
   handle_event → set_state → patch  ◄── dispatchEvent(token, payload)  ◄── Button.onClick
```

- **B2 — boot.** `MainActivity` extracts the bundled Python tree to `filesDir`,
  then `startPython` (JNI) initializes the interpreter off the UI thread and runs
  the entry script. `run_device` blocks in the asyncio loop, so the interpreter
  stays alive for events.
- **B3 — bridge.** `tempest_host.c` registers a built-in `_tempest_host` module
  (`send_to_host` Python→Kotlin, `set_event_sink` to register the event callback)
  and a `dispatchEvent` JNI entry (Kotlin→Python). `PythonRuntime.messageSink` is
  the Kotlin-side hook for everything Python pushes up.
- **B4 — render.** `messageSink` hops to the UI thread and feeds each `mount` /
  `patch` into `TempestTree`, whose `root`/`props`/`children` are Compose snapshot
  state → a granular recomposition of just the affected subtree. `RenderNode`
  (in `TempestRenderer.kt`) maps each node to `Text` / `Button` / `Column` /
  `Row` / `Box`, and turns the JSON-able `Style → Compose` spec (`arrangement` /
  `alignment` / `padding` / `background` / font hints …) into Compose
  `Arrangement` / `Alignment` / `Modifier` at runtime. A `Button` tap calls
  `dispatchEvent(token, payload)` with the handler token straight from the
  serialized `{"$handler": token}` ref.

`TempestRenderer.kt` is the Kotlin counterpart of the Python-side
`to_compose(style)` (`src/tempestroid/renderers/compose/`); the two translators
must agree, which is what the phase-D conformance suite pins.

## Wiring before a build

1. `source ../toolchain/env.sh && ../toolchain/00_fetch_cpython.sh` →
   `../toolchain/dist/python/arm64-v8a/{lib/libpython3.14.so, lib/python3.14/}`.
2. `../toolchain/01_build_wheels.sh` → `../toolchain/dist/wheels/*.whl`, then
   `../toolchain/02_stage_deps.sh` assembles the device `site-packages`.
3. Gradle's `app/build.gradle.kts` tasks copy those into `jniLibs/` and
   `assets/python/`. Point `tempest.pythonPrefix` (in `gradle.properties`) at the
   dist dir.
4. `./gradlew :app:assembleDebug`, then `adb install`.

### Build gotchas (this host works around them)

- **Use the bundled Gradle wrapper 8.11.1** (`./gradlew`), not a global Gradle.
  The env's global Gradle 9.5 is incompatible with AGP 8.7.
- **Export `ANDROID_SDK_ROOT=/usr/lib/android-sdk`** on this host — the SDK/NDK
  live there, not at the stale `ANDROID_HOME`.
- **`ignoreAssetsPattern` is overridden** in `app/build.gradle.kts`. AGP's default
  contains `<dir>_*`, which silently drops asset dirs starting with `_`
  (e.g. `pydantic/_internal/`); the override keeps them.
- **The build renames stdlib `*.gz` → `*.gz-`** so AAPT doesn't auto-decompress
  them; `MainActivity.extractAssets` reverses the guard on extraction.
- **Xiaomi/MIUI device:** enable Developer Options → **"Install via USB"** or
  `adb install` fails with `INSTALL_FAILED_USER_RESTRICTED`.

## Done-when (B2–B4)

- **B2 ✅** — APK boots CPython 3.14 off the UI thread; `import pydantic` /
  `import tempestroid` + a `build` / `serialize_node` round-trip → `python exited
  rc=0`.
- **B3 ✅** — on-device round-trip: `run_device` mounts a counter (`send_to_host`
  → `onMessageFromPython`), an injected `dispatchEvent("1:on_click")` reaches the
  Python handler → `set_state` → patch back up; interpreter stays live.
- **B4 ✅** — Compose renders the mount tree (`Text` / `Button` / `Column` + style
  spec → `Modifier` / `Arrangement`), applies patch batches (recomposes), and a
  **real button tap** → `dispatchEvent` → handler → patch → UI updates
  (`count` 0→N by tapping; verified by screenshot).

## Next (B5–B6, scaffolded)

The renderer is the plug point for the rest of track B: B5 layers a LAN
dev-server + QR code-push onto the same `messageSink`/`dispatchEvent` transport;
B6 adds native capability modules (notifications, camera).
