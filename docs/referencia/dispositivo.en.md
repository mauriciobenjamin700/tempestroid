# Device side (bridge)

The Python half of the device side is hardware-independent and tested without a
phone; the JNI transport (phase B3) and the Kotlin Compose renderer (phase B4)
are implemented in `android-host/` and verified on a real arm64 device.

## `Style → Compose` translator

- **`to_compose(style)`** (`tempestroid.renderers.compose`) — a serializable
  `Style → Compose` spec; the second `Style` translator (pairs with `Style →
  Qt`). Both are pinned by the [conformance suite](../roadmap.md) (phase D).

## Serialization

- **`serialize_node` / `serialize_patch`** — lower the IR/patches to JSON-able
  dicts: handlers become path tokens, `Style` becomes the Compose spec.

## Wire protocol

Messages cross a single marshalling boundary (the JNI bridge on the device, an
in-memory channel in tests).

- **`MountMessage`** — `mount` carries the full serialized tree.
- **`PatchMessage`** — `patch` carries an incremental patch list.
- **`EventMessage`** — `event` carries a device→Python callback addressed by a
  handler token.

A handler token identifies a handler by its node's **path** in the tree plus the
prop name (e.g. `"0/1:on_click"`). It is path-based (not key-based) so the emit
side (serializer) and the dispatch side (registry) compute identical tokens from
the same tree.

## Transport and device app

- **`DeviceApp`** + **`Bridge`** / **`LoopbackBridge`** — wire an `App` to a
  device transport; the device-side analogue of `run_qt`. Events come back by
  handler token, are validated by `parse_event`, and trigger coalesced patches.
- **`JniBridge`** + **`run_device`** — the real on-device transport (phase B3):
  `JniBridge` ships messages to Kotlin via the native `_tempest_host` module;
  `run_device(state, view)` boots a `DeviceApp` on a fresh asyncio loop and
  marshals incoming events back onto it. Imports cleanly off-device (the native
  module is loaded lazily), so the framework still develops/tests on the desktop.

## Dev server — LAN code-push (phase B5)

The Expo-style on-device inner loop: edit on the dev machine, hot-restart on the
phone without rebuilding the APK (`tempest serve <app>`).

- **`DevServer`** — serves the app source (`/version`, `/app`) and relays device
  logs (`/log`) over HTTP.
- **`run_dev_client`** — the device poll loop: fetch on change → re-exec source →
  hot-restart the `DeviceApp`.
- **`serve_device(url)`** — device entry point wiring the real `JniBridge` + the
  native sink + an `urllib` fetch into `run_dev_client`.
- **`render_qr(url)`** — ASCII QR for pairing (falls back to the plain URL).

## Native capabilities (phase B6)

Device-native features driven from Python as `{"kind": "native"}` commands the
Kotlin host routes to capability modules.

- **`notify(title, body="")`** — post a system notification from a handler. The
  extension pattern (`native_command` envelope + a host module router) is in place
  for further capabilities (camera, sensors, …).
