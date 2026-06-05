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
tempest build                 # repackage the prebuilt host with your project
tempest build -o /tmp/app.apk # choose the output path
```

The result lands at `dist/<project>.apk` (or `-o`). `tempest build` bundles your
project, resolves the **prebuilt host APK**, injects the bundle, then re-aligns
(`zipalign`) and re-signs (`apksigner`, debug key). The APK has your project
**baked in** — `adb install` it on any compatible device and the app opens
directly, no server. Debug-signed → installs like any debug build.

!!! note "`build` needs only the SDK build-tools"
    `tempest build`/`run` use only `zipalign` + `apksigner` from the **Android SDK
    build-tools** — **no Gradle, NDK, or `android-host` checkout** — so they work
    from a PyPI install. Run `tempest setup` to check the environment
    (`tempest setup --install` installs the SDK + build-tools).

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
