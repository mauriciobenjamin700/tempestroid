# CLI (`tempest`)

The `tempest` entry point covers the app lifecycle: create, develop in the
simulator, push to the device, package, and inspect the contract.

```bash
uv run tempest new                              # scaffold in the current dir (id = folder name)
uv run python examples/counter/app.py           # run an app directly in the Qt simulator
uv run tempest dev examples/counter/app.py       # dev loop: edit + save → hot reload
uv run tempest deploy examples/multifile/main.py # offline push to a device (no SDK/NDK)
uv run tempest serve examples/device_counter/app.py  # LAN code-push, no APK rebuild
uv run tempest build apk                        # per-app APK, side by side (JDK + SDK)
uv run tempest run                              # build + install on a device + logs
uv run tempest spec                             # print the typed contract (widgets/events) as JSON
uv run tempest --help
```

## Commands

| Command | Status | Description |
|---|---|---|
| `tempest new` | ✅ | Scaffolds a runnable app project **in the current directory** (id = folder name). Pass a name only to create a subdirectory. |
| `tempest dev <app>` | ✅ | Simulator + hot reload / hot restart (needs the `qt` extra). |
| `tempest deploy <app>` | ✅ | **Offline** push of the whole project to a device (no SDK/NDK): install the bundled host + push + launch. |
| `tempest serve <app>` | ✅ | LAN code-push + hot reload of the whole project (phase B5). |
| `tempest install [src]` | ✅ | adb-installs the prebuilt host (no SDK/NDK). |
| `tempest spec` | ✅ | Typed widget/event contract as JSON. |
| `tempest doctor` | ✅ | Diagnose the Android build/run prerequisites (JDK, android-host, SDK, adb, device). Build readiness sets the exit code; a missing device is informational (only `run`/`install` need one). |
| `tempest setup` | ✅ | Configure the build environment: diagnose JDK/SDK/build-tools; `--install` installs the Android SDK. |
| `tempest version` | ✅ | Print the framework version (same as `--version`). |
| `tempest clean` | ✅ | Reset the build caches under `~/.tempestroid` (extracted host natives, bundled-host copy, cloned source) — fixes stale-cache build failures after an upgrade; `--keystore` also drops the cached release keystore. |
| `tempest build [apk\|prd]` | ✅ | `apk`: a **per-app** APK (own id → N apps side by side) via Gradle reusing the prebuilt natives (**JDK + SDK only**, no NDK/toolchain). `prd`: a release AAB. Reads `[tool.tempest]`. |
| `tempest run` | ✅ | `build apk` + install on a device + stream logs. |
| `tempest icon <img>` | ✅ | Generate `icon.png` + `splash.png` from one image (Pillow). |

Apps are **multi-file**: the project tree ships with them (on `sys.path`) in both
the simulator and the device. See [Build, deploy and ship](build.md) for the
difference between the offline push (`deploy`/`serve`) and the distributable APK
(`build`).

## The `tempest dev` cockpit

Interactive commands while the simulator runs:

| Key | Action |
|---|---|
| `r` | Hot reload (state preserved). |
| `R` | Hot restart (clean state). |
| `s` | Raise the window. |
| `q` | Quit. |

Saving the file triggers a hot reload automatically; if the reload is
incompatible with the live state, the loop falls back to a clean restart. A bad
save is caught and printed — the loop survives.

!!! note "build / run need a JDK + the Android SDK"
    `tempest build`/`run` run Gradle reusing the prebuilt natives (the
    `android-host` ships in the package), so they need a **JDK + the Android SDK**
    — **no NDK, no CPython toolchain, no `git clone`**. To run on a device
    **without an SDK**, use `tempest deploy`/`serve`. See
    [Build, deploy and ship](build.md), [installation](../instalacao.md) and the
    [runtime research](../research/android-runtime.md).

## The app-file contract

For `tempest dev`/`serve`, the module must expose:

- `make_state() -> S` — initial-state factory (called on every hot restart).
- `view(app) -> Widget` — the UI builder.

The loader compiles/execs the file fresh on each load (no `.pyc` reuse), so
reloads always see the latest edit. Keep the module free of Qt imports at module
level (use `if __name__ == "__main__"`) so the same file runs on desktop and
device.
