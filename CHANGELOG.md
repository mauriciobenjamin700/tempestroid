# Changelog

All notable changes to **tempestroid** are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`tempest install` — offline device install (no SDK/NDK, no download).** The
  prebuilt CPython + framework host APK now **ships inside the wheel**
  (`tempestroid/_assets/host.apk`), so `tempest install` adb-installs it offline.
  Resolution order: explicit `.apk`/URL → `TEMPESTROID_HOST_APK` → bundled asset
  → `TEMPESTROID_HOST_APK_URL`/GitHub-release download fallback.
- **`tempest new .` scaffolds in place, fully configured.** `tempest new` now
  writes a complete project — `app.py`, `pyproject.toml` (with the
  `tempestroid[qt]` dependency and a `[tool.tempest] app` pointer), `README.md`,
  and `.gitignore`. `.` (the default) targets the current directory; a name
  creates a subdirectory.
- **No-argument app commands.** `tempest dev` / `serve` / `build` / `run` read
  the app path from `[tool.tempest] app` in the nearest `pyproject.toml` when no
  path is passed, so inside a project the commands take no arguments.
- **`tempest serve` closes the device loop.** With a device connected it now
  auto-wires `adb reverse` and launches the host in dev mode pointed at the dev
  server, so `tempest install` + `tempest serve` is the whole on-device flow
  (`--no-launch` to serve only).

### Changed

- **`tempest build` fails with an actionable hint from an installed wheel.**
  When the `android-host` source tree is absent, the error now points at the
  `tempest install` + `tempest serve` device path instead of only mentioning a
  source checkout.

## [0.2.0] — 2026-05-31

### Added

- **Composite component set expanded.** App shell primitives now include
  `AppBar`, `Scaffold`, `NavBar`, `Sidebar`, `Footer`, `Header`, `SafeArea`,
  `Menu`, `Drawer`, `Calendar`, `Clock`, `Card`, `Selection`, `Field`,
  `Feedback`, `Disclosure`, and navigation-focused widgets.
- **Native capability layer.** The Python↔Kotlin bridge now covers
  geolocation, sharing, camera, file storage, clipboard, Bluetooth scan, and
  the request/response native envelope.
- **CLI and device workflow polish.** `tempest build` / `tempest run` became
  more transparent, and the repository now includes a dedicated WSL device-run
  guide for USB/IP + `adb` mirroring.
- **Example and docs refresh.** The gallery and supporting docs were updated
  alongside the new component and device flows.

## [0.1.0] — 2026-05-31

First public release. The framework (Trilho A) is complete and the Android
runtime (Trilho B, phases B0–B6) is validated on a real arm64 device.

### Added

- **Typed declarative UI core.** A frozen-Pydantic `Style` model (`Color`,
  `Edge`, `Border`, `Transition`, and the style enums) and a widget IR
  (`Widget`, `Text`, `Button`, `Column`, `Row`, `Container`, plus value-bearing
  inputs and utility widgets).
- **Renderer-agnostic reconciler** — `build → diff → patch` (`Insert` / `Remove`
  / `Update` / `Reorder` / `Replace`).
- **Qt desktop simulator** (`run_qt`, optional `qt` extra) with a `Style → Qt`
  translator and an asyncio×Qt event loop via `qasync`.
- **Async-first state runtime** (`App`) with coalesced rebuilds and **stateful
  hot reload** (`App.swap_view`).
- **`tempest` CLI** — `dev` (simulator + hot reload/restart cockpit), `serve`
  (LAN code-push to a device), `spec` (typed contract as JSON), `new` (scaffold
  a project), `build` (bundle an app into an APK), `run` (build + install +
  logcat).
- **Android runtime (Trilho B).** Official CPython 3.14 (PEP 738) embedded via a
  hand-rolled JNI bridge in a Kotlin/Gradle host; native wheels (`pydantic-core`)
  via cibuildwheel; a Jetpack Compose renderer; a LAN dev server with QR pairing;
  and native capabilities (notifications).
- **Conformance suite** pinning the Qt and Compose `Style` translators with
  golden snapshots (phase D).

[Unreleased]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mauriciobenjamin700/tempestroid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mauriciobenjamin700/tempestroid/releases/tag/v0.1.0
