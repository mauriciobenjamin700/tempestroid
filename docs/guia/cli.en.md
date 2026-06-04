# CLI (`tempest`)

The `tempest` entry point covers the app lifecycle: create, develop in the
simulator, push to the device, package, and inspect the contract.

```bash
uv run tempest new MyApp                        # scaffold a new app project
uv run python examples/counter/app.py           # run an app directly in the Qt simulator
uv run tempest dev examples/counter/app.py       # dev loop: edit + save → hot reload
uv run tempest deploy examples/multifile/main.py # offline push to a device (no SDK/NDK)
uv run tempest serve examples/device_counter/app.py  # LAN code-push, no APK rebuild
uv run tempest build MyApp/main.py              # standalone shippable APK (needs SDK/NDK)
uv run tempest run MyApp/main.py                # build + install on a device + logs
uv run tempest spec                             # print the typed contract (widgets/events) as JSON
uv run tempest --help
```

## Commands

| Command | Status | Description |
|---|---|---|
| `tempest new <name>` | ✅ | Scaffolds a runnable app project. |
| `tempest dev <app>` | ✅ | Simulator + hot reload / hot restart (needs the `qt` extra). |
| `tempest deploy <app>` | ✅ | **Offline** push of the whole project to a device (no SDK/NDK): install the bundled host + push + launch. |
| `tempest serve <app>` | ✅ | LAN code-push + hot reload of the whole project (phase B5). |
| `tempest install [src]` | ✅ | adb-installs the prebuilt host (no SDK/NDK). |
| `tempest spec` | ✅ | Typed widget/event contract as JSON. |
| `tempest setup` | ✅ | Configure the build environment: diagnose JDK/SDK/NDK/build-tools/toolchain; `--install` installs the Android SDK + NDK. |
| `tempest build <app>` | ✅ | **Standalone shippable APK** with the project baked in (needs Android SDK/NDK). |
| `tempest run <app>` | ✅ | Build + install on a device + stream logs. |

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

!!! note "build / run need the Android toolchain"
    `tempest build`/`run` drive the `android-host` Gradle project + `adb`, so they
    require an Android SDK/NDK and a checkout of the host tree. To run on a device
    **without** a toolchain, use `tempest deploy`/`serve`. See
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
