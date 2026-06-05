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
| **Ship an APK** for someone to test | `tempest build` | SDK build-tools | Self-contained, distributable `.apk` |
| Build + install + logs | `tempest run` | SDK build-tools + adb | Installs the APK and tails logs |

!!! info "Two philosophies"
    - **Push (ephemeral)** (`deploy`/`serve`): a **generic host** (CPython +
      framework) is installed once; your Python is pushed on top. Fast, offline.
      But the app lives **inside the host** — it is not an artifact you can hand
      to someone else.
    - **Shippable APK** (`build`/`run`): **repackage the prebuilt host** with your
      project injected (re-signed via the SDK's `zipalign`/`apksigner`). **No
      Gradle, NDK, or `android-host` checkout** — just the SDK build-tools. This
      is the path that yields a distributable `.apk`.

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
    something distributable, use [`tempest build`](#ship-an-apk).

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

## Ship an APK

To produce a **self-contained** `.apk` (runs with no dev server, hand it to
anyone):

```bash
tempest build                              # Gradle: APK with its own applicationId
tempest build --app-id com.yourco.app      # set the id (recommended for anything real)
tempest build -o /tmp/app.apk              # choose the output path
```

The result lands at `dist/<project>.apk` (or `-o`). By default `tempest build`
runs Gradle (`assembleDebug`) and stamps each app with its **own `applicationId`**
+ launcher label, so two tempestroid apps **install side by side** instead of
overwriting each other. Debug-signed → `adb install` it on any compatible device
and the app opens directly, no server.

!!! info "Do I set `--app-id`, or does the framework generate it?"
    **Both — but for anything real, set your own.**

    - You pass `--app-id com.yourco.app` → that's the `applicationId` (and
      `--app-name "My App"` for the name under the icon).
    - You **omit** it → the framework **derives** `com.example.<project-name>`,
      just so you can build and install right away without deciding anything.

    The derived `com.example.*` id is a **placeholder, not publishable** — the
    Play Store rejects `com.example.*`. Rule of thumb: **test with the derived id;
    set your own `--app-id`** (your company's reverse domain, e.g.
    `com.yourco.app`) **as soon as the app is real**, and **keep the same id
    forever** — changing it makes Android/Play treat it as a different app (loses
    updates and data). The id is independent of the internal Java/JNI package
    (`org.tempestroid.host`), so choosing your own never breaks the bridge.

!!! note "Default `build` uses the toolchain; `--fast` skips it (1 app)"
    Default `tempest build` runs Gradle, so it needs the SDK **+ NDK** + the
    `android-host` checkout + the CPython toolchain — the CLI **prepares whatever
    is missing**. To iterate fast on a **single** app without the toolchain, use
    `tempest build --fast`: it skips Gradle and **repackages the prebuilt host**
    (just the SDK build-tools, works from a PyPI install). Trade-off: `--fast`
    keeps the shared `org.tempestroid.host` id (an APK repackage can't rewrite the
    binary manifest's package), so it is for **one app at a time**, not several
    side by side. Run `tempest setup --install` for the SDK/NDK.

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

!!! tip "The splash covers the CPython boot"
    The interpreter takes a few seconds to start. The splash is drawn by the
    Activity from **assets** and stays on screen **until your app's first
    `mount`** — so the user sees your brand, not a blank screen. Because it lives
    in assets (a stable path), `--splash`/`--splash-bg` work on **every** build
    path, including `--fast`.

## Publish to the Play Store (`--release` → AAB)

The Play Store requires an **Android App Bundle** (`.aab`), release-signed, with
your own `applicationId`. `tempest build --release` produces that via Gradle
`bundleRelease` and **prepares whatever is missing** (SDK/NDK, source checkout,
CPython toolchain, keystore):

```bash
tempest build main.py --release \
  --app-id com.yourcompany.todo \
  --app-version 1.0.0 \
  --version-code 1 \
  --keystore release.jks          # omit → generates ~/.tempestroid/release.jks
# → dist/<project>-release.aab  (upload to the Play Console)
```

!!! warning "Keep the keystore"
    The release keystore signs your app. **Losing it blocks future Play updates.**
    Back up `--keystore` (or the generated `~/.tempestroid/release.jks`). Use your
    **own** `--app-id` — the `com.example.*` placeholder won't publish.

!!! info "`--release` needs the full toolchain"
    Unlike the debug APK (repackage), the AAB is a from-source build: it needs the
    SDK **+ NDK** + an `android-host` checkout + the staged CPython toolchain. The
    CLI installs/clones/stages what's missing (the CPython staging is heavy:
    downloads + native wheel build).

## Environment setup

!!! tip "Let `tempest setup` configure it for you"
    ```bash
    tempest setup            # diagnose JDK/SDK/NDK/build-tools/toolchain + plan
    tempest setup --install  # install the Android SDK + NDK (needs a JDK)
    ```
    `tempest setup` (no flag) reports what's missing and how to fix it. With
    `--install` it downloads the command-line tools, accepts the licenses, and
    installs `platform-tools` + `platforms;android-35` + `build-tools;35.0.0` +
    `ndk;27.3.13750724` into a managed directory (`--sdk-dir` to choose). The
    **JDK** and `make toolchain` stay guided (not auto-installed).

For the toolchain paths (`build`/`run`), the build host needs:

- **Android SDK + NDK.** Export `ANDROID_SDK_ROOT` pointing at the SDK (on this
  reference host: `/usr/lib/android-sdk`, **not** the stale `ANDROID_HOME`):

    ```bash
    export ANDROID_SDK_ROOT=/usr/lib/android-sdk
    ```

- **JDK 21** (`java -version`).
- **Gradle wrapper 8.11.1** (`android-host/gradlew`) — the global Gradle 9.x is
  incompatible with AGP 8.7; **always** use the wrapper (the `tempest` commands
  already do).
- The **staged Python toolchain**: CPython 3.14 + native wheels
  (`pydantic-core`) under `toolchain/dist/`. Generate with:

    ```bash
    make toolchain
    ```

On the **device**: enable **USB debugging**; on MIUI/HyperOS (Xiaomi/Redmi/POCO)
also enable **"Install via USB"**, or `adb install` fails with
`INSTALL_FAILED_USER_RESTRICTED`.

!!! tip "One-command diagnosis"
    `tempest doctor` runs the preflight (host tree, SDK, `adb`, device) and points
    at what is missing before a build. On WSL? See the dedicated
    [device-over-USB (WSL)](dispositivo-wsl.md) guide.

## Send the APK for someone to test

1. Build: `tempest build` (or `--release`).
2. Grab the `.apk` at `android-host/app/build/outputs/apk/debug/app-debug.apk`.
3. Send the file (messenger, link, etc.).
4. They install it (`adb install app-debug.apk`, or opening the `.apk` on the
   device with "unknown sources" allowed).

The app runs standalone — without your computer, without a dev server.

## Recap

- Apps are **multi-file**: the project tree ships with them, on `sys.path`, in
  both the simulator and the device.
- `tempest deploy` / `serve` run on **your** device **without a toolchain** —
  great for testing, but yield no artifact.
- `tempest build` yields a **distributable, self-contained APK** — needs SDK/NDK +
  an `android-host` checkout.
- `tempest doctor` validates the environment; the [WSL guide](dispositivo-wsl.md)
  covers USB passthrough.
