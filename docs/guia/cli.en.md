# CLI (`tempest`)

The `tempest` entry point covers the app lifecycle: create, develop in the
simulator, push to the device, package, and inspect the contract.

```bash
uv run tempest new MyApp                        # scaffold a new app project
uv run python examples/counter/app.py           # run an app directly in the Qt simulator
uv run tempest dev examples/counter/app.py       # dev loop: edit + save → hot reload
uv run tempest serve examples/device_counter/app.py  # LAN code-push, no APK rebuild
uv run tempest build MyApp/app.py               # bundle the app into an APK
uv run tempest run MyApp/app.py                 # build + install on a device + logs
uv run tempest spec                             # print the typed contract (widgets/events) as JSON
uv run tempest --help
```

## Commands

| Command | Status | Description |
|---|---|---|
| `tempest new <name>` | ✅ | Scaffolds a runnable app project. |
| `tempest dev <app>` | ✅ | Simulator + hot reload / hot restart (needs the `qt` extra). |
| `tempest serve <app>` | ✅ | LAN code-push to a device + log relay (phase B5). |
| `tempest spec` | ✅ | Typed widget/event contract as JSON. |
| `tempest build <app>` | ✅ | Bundles an app into an APK (needs Android SDK/NDK). |
| `tempest run <app>` | ✅ | Build + install on a device + stream logs. |

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
    require an Android SDK/NDK and a checkout of the host tree. See
    [installation](../instalacao.md) and the [runtime research](../research/android-runtime.md).

## The app-file contract

For `tempest dev`/`serve`, the module must expose:

- `make_state() -> S` — initial-state factory (called on every hot restart).
- `view(app) -> Widget` — the UI builder.

The loader compiles/execs the file fresh on each load (no `.pyc` reuse), so
reloads always see the latest edit. Keep the module free of Qt imports at module
level (use `if __name__ == "__main__"`) so the same file runs on desktop and
device.
