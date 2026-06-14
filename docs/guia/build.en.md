# Build, deploy and ship

This page shows how to leave the simulator and **run your app on an Android
device** — from a quick test on your own phone to producing a **self-contained
APK** you hand to someone else. All from your Python project.

!!! tip "Start in the simulator"
    For the edit → see loop, use `tempest dev` (the [Qt simulator](cli.md)). This
    page is about taking the same app to a **device** and to a **shippable APK**.

## Multi-file projects

Your app is rarely a single file: `main.py` imports sibling modules and packages
from your project tree. tempestroid handles this transparently.

The **project root** is the nearest ancestor of the app file containing a
`pyproject.toml`. The whole importable tree under it is bundled and placed on
`sys.path` — in the simulator **and** on the device — so:

```python
# main.py
from my_package.widgets import card   # ✅ resolves the same on desktop and device
```

resolves identically on both sides. The bundle **excludes** non-app code:
`.venv`, `__pycache__`, `.git`, `dist`, `build`, editor/lint caches.

!!! example "Typical project layout"
    ```text
    my-app/
    ├── pyproject.toml      # has [tool.tempest] app = "main.py"
    ├── main.py             # defines view(app) + make_state()
    └── my_package/
        ├── __init__.py
        └── widgets.py      # imported by main.py
    ```

    The `pyproject.toml` anchors the root. Without one, the root is `main.py`'s
    own directory (single-file mode).

```toml
# pyproject.toml
[tool.tempest]
app = "main.py"
```

With `[tool.tempest] app` set, `dev` / `deploy` / `serve` / `build` / `run` take
no path argument inside the project.

## Which command?

| I want to… | Command | Needs what? | Yields |
|---|---|---|---|
| Run quickly on **my** device | `tempest deploy` | nothing (just adb) | App running on the device (ephemeral) |
| Edit + see live (hot reload) | `tempest serve` | nothing (just adb) | LAN code-push loop |
| **Ship an APK** to someone | `tempest build apk` | JDK + Android SDK | `.apk` with its own `applicationId` (**N apps side by side**) |
| Distribute **off the Play Store** (site, link) | `tempest build release-apk` | JDK + SDK + keystore | Release-signed `.apk` with **your** key |
| Build + install + logs | `tempest run` | JDK + SDK + adb | Installs the APK and tails logs |
| Publish to the Play Store | `tempest build prd` | JDK + SDK + keystore | Release-signed `.aab` |
| Iterate on one app, **no SDK install** | `tempest build --fast` | SDK build-tools only | `.apk` (shared id, one app) |

!!! info "How it works (no heavy toolchain)"
    `tempest build apk` runs **Gradle** (which stamps the `applicationId` + every
    provider authority per app → they **install side by side, no collisions**) but
    **reuses the prebuilt host natives** (`libpython`, the stdlib, the JNI shim)
    that ship in the package. So it needs only a **JDK + the Android SDK** — **no
    NDK, no compiling CPython**. The `android-host` project ships **inside the
    wheel**, so it works from a plain `pip install` with **no `git clone`**.

    - `deploy`/`serve`: push your code to a **generic host** that is installed
      once (fast, offline) — the app lives inside the host, not a shippable artifact.
    - `--fast`: repackage the prebuilt host with **no SDK at all** (just
      build-tools), but a shared `org.tempestroid.host` id → **one app per device**.
    - `--from-source`: the heavy build that stages the CPython toolchain (rarely
      needed).

## Run on my device (no toolchain)

You do **not** need an Android SDK/NDK or the `android-host` source to test on
your own phone. Connect the device (`adb devices` should list it) and:

```bash
tempest deploy            # install the bundled host (once) + push the project + launch
```

`tempest deploy`:

1. Installs the **prebuilt host** (downloaded from the GitHub release on first
   use, then cached) if it is not on the device yet. Repeat runs skip the step.
2. Bundles your project and pushes it **once** over a short-lived server.
3. Launches the app and **exits**. The app keeps running on the device.

!!! warning "`deploy` yields no artifact"
    The app pushed by `deploy` lives in the host session. On a cold boot, or on
    someone else's phone, the host runs the built-in demo — **not** your app. For
    something distributable, use [`tempest build apk`](#build-an-apk-tempest-build-apk).

For a **hot-reload loop** (edit + save → reloads on device):

```bash
tempest install           # just adb-install the host (offline/bundled)
tempest serve             # LAN code-push: saving any file reloads on device
```

`tempest install` resolves the host APK in order: explicit `.apk` path/URL →
`TEMPESTROID_HOST_APK` → a bundled asset (only in a source checkout staged with
`make stage-host`) → a download from the GitHub release
(`TEMPESTROID_HOST_APK_URL` to override), cached under `~/.cache/tempestroid`. The
PyPI wheel does **not** embed the ~100 MB APK, so the download is the normal path
from a PyPI install (offline thereafter).

## Build an APK (`tempest build apk`)

To produce a **self-contained** `.apk` (runs with no dev server, with your
project's **own id** → installs side by side with any other tempestroid app):

```bash
tempest build apk          # reads [tool.tempest], writes dist/<project>.apk
tempest build apk -o /tmp/app.apk
```

Identity + look come from **`[tool.tempest]`** in pyproject.toml — no flag soup:

```toml
[tool.tempest]
app = "app.py"
id = "com.yourcompany.todolist"  # applicationId; derived from the project if omitted
name = "Todo List"               # name under the icon
icon = "icon.png"                # optional
splash = "splash.png"            # optional
splash_bg = "#0b0f14"            # optional
version = "1.0.0"                # optional (default 1.0.0)
```

The result lands at `dist/<project>.apk`, debug-signed → `adb install` it on any
device and it opens directly, no server. Each project carries its **own
`applicationId`**, so **N apps install side by side** (never overwriting). The
`--app-id`/`--app-name`/`--icon`/… flags override the config per build.

!!! info "Do I set `id`, or does the framework generate it?"
    **Both — but for anything real, set your own.** Omitted → the framework
    **derives** `com.example.<project>` just so you can build right away. That
    `com.example.*` is a **placeholder, not publishable** (the Play Store rejects
    it). Rule: **test with the derived id; set your own `id`** (your reverse
    domain, e.g. `com.yourco.app`) and **keep it forever** — changing it makes
    Android/Play treat it as a different app. The `id` is independent of the
    internal Java/JNI package (`org.tempestroid.host`), so choosing your own
    never breaks the bridge.

!!! note "Needs only JDK + Android SDK (no NDK, no toolchain)"
    `tempest build apk` runs Gradle **reusing the prebuilt host natives**
    (libpython/JNI/stdlib shipped in the package) → it **does not compile CPython
    and needs no NDK**. The `android-host` project ships **inside the wheel**, so
    it works from a plain `pip install` with **no `git clone`**. Run `tempest
    setup --install` once for the SDK (the JDK is a prerequisite). Without JDK/SDK
    the build **falls back to `--fast`** (shared id) with a warning instead of
    failing.

## App icon and boot splash

Every APK already ships a default **tempestroid icon** and a **splash** that
covers the Python interpreter's boot (a few seconds). To customise per app:

```bash
tempest build --icon icon.png \
  --splash splash.png \
  --splash-bg "#0b0f14"
```

!!! tip "Generate both from ONE image with `tempest icon`"
    Don't want to size them by hand? Point at a logo and the CLI writes both PNGs:

    ```bash
    tempest icon logo.png --out assets
    # → assets/icon.png (square) + assets/splash.png (centered, transparent bg)
    tempest build --icon assets/icon.png --splash assets/splash.png --splash-bg "#0b0f14"
    ```

    Needs Pillow: `pip install tempestroid[icons]` (or `uv add tempestroid[icons]`).

- `--icon icon.png` — the launcher icon (shown in the app drawer). **Gradle build
  only** (the default): the icon is a *compiled* resource, and a `--fast`
  repackage can't rewrite `resources.arsc`, so with `--fast` the app keeps the
  default icon (the CLI warns).
- `--splash splash.png` — the image shown centered while Python starts.
- `--splash-bg "#rrggbb"` — the splash background colour (default `#0b0f14`).

### Adaptive icon (the launcher mask)

A plain square PNG doesn't get the launcher mask (rounded / squircle corners).
For a real **adaptive icon** — two layers, foreground + background, that the
launcher masks like a native app — generate the foreground layer and pass it to
the build:

```bash
tempest icon logo.png --adaptive --out assets
# → also writes assets/ic_launcher_foreground.png (the mark centered in the safe zone)
tempest build --adaptive-icon assets/ic_launcher_foreground.png --icon-bg "#0b0f14"
```

- `--adaptive-icon fg.png` — the **foreground** layer (the mark, with safe-zone
  margin). **Gradle build only** (a compiled resource; `--fast` keeps the default
  icon and warns).
- `--icon-bg "#rrggbb"` — the adaptive-icon **background** colour (default white).

!!! info "What the build generates"
    It emits a real Android adaptive icon: `res/drawable/ic_launcher_foreground.png`
    + `res/values/ic_launcher_background.xml` (the colour) + the
    `res/mipmap-anydpi-v26/ic_launcher{,_round}.xml` that redirect
    `@mipmap/ic_launcher` to them on Android 8+ (API 26). On older versions the
    square PNG (`--icon`) still applies.

!!! tip "The splash covers the CPython boot"
    The interpreter takes a few seconds to start. The splash is drawn by the
    Activity from **assets** and stays on screen **until your app's first
    `mount`** — so the user sees your brand, not a blank screen. Because it lives
    in assets (a stable path), `--splash`/`--splash-bg` work on **every** build
    path, including `--fast`.

## Heavy native capabilities are opt-in (lean APK)

The APK weight does not come from Python (the CPython stdlib is already trimmed at
build time) but from the **heavy Android dependencies**: camera, QR scanner
(ML Kit), push (Firebase), video (media3) and maps. So they are **optional** — the
default build bundles **none of them**, cutting the debug APK from **~58 MB to
~47 MB (−11.4 MB)**. You re-enable only what the app uses:

```toml
# pyproject.toml
[tool.tempest]
features = ["camera", "qr"]   # bundle only camera + QR scanner
```

or on the command line (repeatable):

```bash
tempest build --feature camera --feature qr
```

| Feature | Enables |
| --- | --- |
| `camera` | `CameraPreview` widget + `take_photo`/`record_video` |
| `qr` | `QrScanner` widget (transitively pulls in `camera`) |
| `push` | push notifications via FCM |
| `video` | `VideoPlayer` widget |
| `maps` | `MapView` widget |

!!! info "Each feature needs a from-source build (SDK/NDK)"
    A prebuilt APK cannot receive new Gradle dependencies, so any `--feature`
    automatically turns on the `--from-source` path (needs the Android SDK + NDK).
    The **lean default** (no features) keeps using the prebuilt host — zero toolchain.

!!! tip "Without the feature, the widget becomes a placeholder"
    If the app uses a `CameraPreview`/`QrScanner`/`VideoPlayer`/`MapView` but the
    feature wasn't bundled, it renders a labeled placeholder instead of crashing; a
    non-bundled native call raises `NativeError("feature_not_built")`.

The PyPI extras mirror the features (`pip install tempestroid[camera]`) purely as
**intent documentation** — what actually trims the APK is the build flag above, not
pip.

## Distribute off the Play Store (`tempest build release-apk` → signed APK)

To ship the app through a **website, an alternative store, or a direct link** —
without going through the Play Store — you want a **release-signed APK signed with
your own key** (not the debug-signed `tempest build apk`, which is for testing
only). That's `tempest build release-apk`: it runs Gradle `assembleRelease` with
your keystore.

```bash
tempest build release-apk                          # uses [tool.tempest] id/name/version
tempest build release-apk --keystore release.jks   # your keystore (else ~/.tempestroid/release.jks)
tempest build release-apk --app-id com.acme.app --app-version 1.2.0
# → dist/<project>-release.apk
```

Verify the signature with the SDK's `apksigner`:

```bash
apksigner verify --print-certs dist/<project>-release.apk
```

!!! warning "Real build required (no `--fast` fallback)"
    Unlike `tempest build apk`, `release-apk` does **not** fall back to the
    `--fast` repackage when the toolchain is missing — a release-signed APK
    requires the real Gradle build. Without JDK + SDK it fails with an error
    (resolve the toolchain with `tempest setup --install`).

!!! note "Same keystore as `prd`"
    Reuses `prd`'s keystore and its warning below: **back up the key** and **set
    your own `id`** before distributing.

## Publish to the Play Store (`tempest build prd` → AAB)

The Play Store requires a release-signed **Android App Bundle** (`.aab`).
`tempest build prd` produces it via Gradle `bundleRelease`, reading `[tool.tempest]`
and using a keystore (yours via `--keystore`, else a generated cached one):

```bash
tempest build prd                          # uses [tool.tempest] id/name/version
tempest build prd --keystore release.jks   # your keystore (else ~/.tempestroid/release.jks)
# → dist/<project>-release.aab  (upload to the Play Console)
```

!!! warning "Keep the keystore + set your id"
    The release keystore signs your app. **Losing it blocks future Play updates** —
    back up `--keystore` (or the generated `~/.tempestroid/release.jks`). And set
    your own `id` in `[tool.tempest]` — the `com.example.*` placeholder won't
    publish.

!!! note "Same light base as `apk`"
    Like `apk`, `prd` reuses the prebuilt host natives → **JDK + Android SDK only**,
    no NDK or CPython toolchain. (To build the toolchain from scratch, the advanced
    `--from-source` flag exists.)

## Environment setup

!!! tip "Let `tempest setup` configure it for you"
    ```bash
    tempest setup            # diagnose JDK/SDK/build-tools + plan
    tempest setup --install  # install the Android SDK (needs a JDK)
    ```
    `tempest setup` (no flag) reports what's missing and how to fix it. With
    `--install` it downloads the command-line tools, accepts the licenses, and
    installs the SDK into a managed directory (`--sdk-dir` to choose). The **JDK**
    stays guided (not auto-installed).

`tempest build apk`/`prd`/`run` need:

- **A JDK** (`java -version`) — a prerequisite (guided, not installed by the CLI).
- **The Android SDK.** `tempest setup --install` installs/configures it; or export
  `ANDROID_SDK_ROOT` to an existing SDK. **No NDK needed** (the build reuses the
  prebuilt natives).

!!! note "Advanced `--from-source` path"
    Only with `--from-source` does the build stage the heavy toolchain (CPython
    3.14 + native wheels via `make toolchain`) and need the **NDK** + the Gradle
    wrapper 8.11.1. The normal (prebuilt) flow needs none of that.

On the **device**: enable **USB debugging**; on MIUI/HyperOS (Xiaomi/Redmi/POCO)
also enable **"Install via USB"**, or `adb install` fails with
`INSTALL_FAILED_USER_RESTRICTED`.

!!! tip "One-command diagnosis"
    `tempest doctor` runs the preflight (host tree, SDK, `adb`, device) and points
    at what is missing before a build. On WSL? See the dedicated
    [device-over-USB (WSL)](dispositivo-wsl.md) guide.

## APK size

Almost all of the APK weight is the **embedded CPython 3.14** (the native `.so`s
+ the standard library) plus the native `pydantic_core` — all required at
runtime. The build already ships a **lean** APK: heavy optional dependencies are
*feature-gated* (`tempest.features` — camera/QR/video/push are only pulled in
when asked for), the icons use only `material-icons-core`, and the standard
library is pruned before it becomes an asset.

Breakdown of a *lean* debug APK (arm64-v8a, no extra features):

| Component | Size (in APK) | Removable? |
| --- | --- | --- |
| `lib/arm64-v8a/*.so` (libpython, libcrypto, libsqlite, libssl) | ~11 MB | ❌ runtime (already stripped) |
| `site-packages/pydantic_core` (native wheel) | ~4.6 MB | ❌ runtime |
| `site-packages/pydantic` | ~2.0 MB | ❌ runtime |
| `lib-dynload/*.so` (stdlib extension modules) | ~6.6 MB | partial — test ones only |
| pure stdlib (`asyncio`, `email`, `json`, `re`, …) | ~6 MB | partial |
| Compose/AndroidX + DEX + resources | ~3 MB | ❌ runtime |

!!! info "What gets pruned (F6)"
    `CopyPythonStdlibTask` in `android-host/app/build.gradle.kts` excludes from the
    **assets** (it never touches the dev prefix) everything an app does not use at
    runtime: the test suites (`test/`), the IDLE editor, Tk/turtle, the packaging
    tooling (`ensurepip`/`venv`/`lib2to3`), `pydoc_data`, the bytecode caches,
    **plus** the interactive REPL (`_pyrepl`), the WSGI reference server
    (`wsgiref`), `doctest.py`/`pydoc.py` and CPython's **test extension modules**
    (`lib-dynload/_test*.so`, `_xxtestfuzz`, `xxsubtype`, `xxlimited*`). None are
    imported by the framework or `pydantic` (verified off-device with an import
    trace).

!!! note "Why it doesn't drop below ~38 MB"
    The natives (`libpython3.14.so` 5.8 MB, `libcrypto` 3.7 MB) already ship
    stripped (running `llvm-strip` saves 0 bytes) and `pydantic_core`/`pydantic`
    are mandatory. What's left to prune safely is test dead-weight, which
    compresses well in the zip — so the net gain is modest (~1 MB). Bigger cuts
    (compressing the stdlib into a single archive, dropping the CJK codecs) would
    require touching the Kotlin/C host and on-device validation — out of scope for
    this offline phase.

## Send the APK for someone to test

1. Build: `tempest build apk`.
2. Grab the `.apk` at `dist/<project>.apk`.
3. Send the file (messenger, link, etc.).
4. They install it (`adb install <project>.apk`, or opening the `.apk` on the
   device with "unknown sources" allowed).

The app runs standalone — without your computer, without a dev server.

## Recap

- Apps are **multi-file**: the project tree ships with them, on `sys.path`, in
  both the simulator and the device.
- `tempest deploy` / `serve` run on **your** device **without any SDK** — great
  for testing, but yield no artifact.
- `tempest build apk` yields a **distributable, per-app APK** (its own id → N apps
  side by side) — needs only **JDK + Android SDK** (no NDK, no CPython toolchain;
  `android-host` ships in the wheel). Identity + branding from `[tool.tempest]`.
- `tempest build prd` is the store-ready release AAB.
- `tempest doctor` validates the environment; the [WSL guide](dispositivo-wsl.md)
  covers USB passthrough.
