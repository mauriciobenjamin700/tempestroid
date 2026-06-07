# Installation

There are **two audiences** for tempestroid, and each installs differently:

- **You want to build an app** with the framework → [End users](#end-users).
- **You want to contribute** to the framework itself (work on this repository's
  code) → [Contributors](#contributors-this-repository).

Start with the section that matches your case — they are independent.

## End users

You only **use** the framework to build apps. Install with `pip` (or `uv pip`).
The **core** depends only on `pydantic`:

```bash
pip install tempestroid
```

### Optional extras

Install only what your workflow needs:

```bash
pip install "tempestroid[qt]"      # desktop simulator (PySide6 + qasync)
pip install "tempestroid[icons]"   # icon/splash generator (tempest icon — Pillow)
```

| Extra | Adds | When to use |
|---|---|---|
| (core) | just `pydantic` | always — the typed widget tree |
| `qt` | `PySide6` + `qasync` | run/preview the app in the **desktop simulator** (`tempest dev`/`run`) |
| `icons` | `Pillow` | generate `icon.png` + `splash.png` from one image (`tempest icon`) |

!!! tip "Start with the simulator"
    To try it out without any Android device, install the `qt` extra and run
    `tempest dev myapp/app.py` — the app shows up in a desktop window with hot
    reload. See the [Quick start](inicio-rapido.md).

### Building for Android

Producing the **APK** (`tempest build apk`) needs only a **JDK** and the
**Android SDK** — **no** NDK, no CPython toolchain, no cloning this repository.
The `android-host` project that builds the APK **ships inside the pip package**.

```bash
pip install tempestroid          # already bundles the android-host
tempest setup --install          # install the Android SDK (if missing)
tempest doctor                   # diagnose what's missing (JDK, SDK, adb, device)
tempest new myapp && cd myapp
tempest build apk                # its own APK (installs side by side with others)
```

!!! info "JDK + SDK, and that's it"
    The APK reuses the host's already-compiled native binaries (embedded
    CPython), so it skips the NDK/toolchain. `tempest doctor` separates what's
    needed to **build** (JDK + SDK) from what's only for **running/installing**
    (adb + a device). Details in [Build, deploy & publish](guia/build.md).

| Target | Needs |
|---|---|
| Simulator (desktop) | Python ≥ 3.11 + the `qt` extra |
| Building the APK | JDK + Android SDK (`tempest setup --install`) — no NDK/toolchain |
| Install/run on a device | the above + `adb` + a connected device |

## Contributors (this repository)

You'll work on the **framework code**. The workflow uses
[uv](https://docs.astral.sh/uv/); a single command installs everything:

```bash
git clone https://github.com/mauriciobenjamin700/tempestroid
cd tempestroid
uv sync        # core + dev tooling + Qt simulator + docs
```

Beyond the runtime dependencies, `uv sync` installs:

- the dev group (`ruff`, `pyright`, `pytest`, `pytest-asyncio`);
- the Qt simulator (`PySide6`, `qasync`) — part of the dev/test loop;
- the documentation site (`mkdocs-material` + the language plugin).

### Quality gates

Run before every commit (or use the `Makefile`):

```bash
make gate        # ruff + pyright(strict) + pytest + mkdocs --strict + conventions
make quick       # fast version (no pytest)
make docs-sync   # checks README/CLI/phase-table stay in sync
```

### Documentation

The site (this content) is built with MkDocs Material, installed by `uv sync`:

```bash
uv run mkdocs serve              # local server with hot reload at http://127.0.0.1:8000
uv run mkdocs build --strict     # production build; fails on any warning
```

The header includes a **PT-BR / EN-US language switcher** (`mkdocs-static-i18n`
plugin).
