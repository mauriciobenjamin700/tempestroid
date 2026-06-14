# Running on a device from WSL

Guide to connect a physical Android device to a **WSL 2** (Windows) session,
build the `android-host/` and install/run the app on the device. Covers the
**usbipd-win** setup (USB passthrough into WSL) and the `adb` workaround under
WSL's **mirrored** networking mode.

## Prerequisites

On the **build host** (WSL):

- Android SDK + NDK. On this host they live at `/usr/lib/android-sdk` (not the
  stale `ANDROID_HOME`), so export `ANDROID_SDK_ROOT=/usr/lib/android-sdk`.
- JDK 21 (`java -version`).
- Gradle **wrapper 8.11.1** (`android-host/gradlew`) — the global Gradle 9.x is
  incompatible with AGP 8.7; always use the wrapper.
- The staged Python toolchain (`make toolchain`): CPython 3.14 + wheels +
  `toolchain/dist/`. See the [Android runbook](../research/android-runbook.md).

On the **device**:

- **Developer options** → **USB debugging** on.
- On MIUI/HyperOS (Xiaomi/Redmi/POCO): also enable **"Install via USB"**,
  otherwise `adb install` fails with `INSTALL_FAILED_USER_RESTRICTED`.

On **Windows**:

- **usbipd-win** installed (step below).

## 1. Install usbipd-win (Windows)

In an **admin PowerShell**:

```powershell
winget install usbipd
```

If `winget` can't find it, download the `.msi` from the
[official release](https://github.com/dorssel/usbipd-win/releases/latest),
install it and **close/reopen PowerShell** (so `PATH` refreshes).

## 2. Attach the device to WSL (Windows)

With the cable connected and USB debugging on, in the admin PowerShell:

```powershell
usbipd list
```

```text
Connected:
BUSID  VID:PID    DEVICE                     STATE
1-7    2717:ff08  Redmi 12                   Not shared
...
```

Take the device's `BUSID` (e.g. `1-7`), then:

```powershell
usbipd bind --busid 1-7
usbipd attach --wsl --busid 1-7
```

- `bind` only the **first time** (marks the device shareable).
- `attach` every time you reconnect the cable (attaches the device to WSL).

Confirm in WSL that the kernel saw the device:

```bash
dmesg | grep -i "Product:\|SerialNumber:" | tail -3
# usb 1-1: Product: Redmi 12
# usb 1-1: SerialNumber: 0d474c147d75
```

## 3. adb workaround under mirrored networking

Under WSL 2's **mirrored** networking mode, `adb start-server` **hangs**: the
daemon's readiness handshake over loopback `127.0.0.1:5037` never completes
(`adb devices`/`adb kill-server` hang and time out).

Workaround: start the server in the **foreground** (`nodaemon`) as a persistent
background process and let client commands talk to it:

```bash
# 1. start the server in the background (leave it running):
ANDROID_SDK_ROOT=/usr/lib/android-sdk \
  /usr/lib/android-sdk/platform-tools/adb nodaemon server &

# 2. the client now responds normally:
adb devices -l
# List of devices attached
# 0d474c147d75   device  product:fire_global model:23053RN02A ...
```

If `adb` wedges again, kill all processes and repeat:

```bash
pkill -9 adb
```

## 4. Build and install

From the repository root:

```bash
export ANDROID_SDK_ROOT=/usr/lib/android-sdk
make apk            # ./gradlew :app:assembleDebug — produces app-debug.apk (~49 MB)
make install        # adb install -r of the APK onto the device
# or both at once:
make apk-install
```

Raw equivalent (with an explicit serial, handy with the `nodaemon` server):

```bash
cd android-host && ANDROID_SDK_ROOT=/usr/lib/android-sdk ./gradlew :app:assembleDebug
adb -s 0d474c147d75 install -r app/build/outputs/apk/debug/app-debug.apk
```

> The build stages Python from `toolchain/dist/` (symlink or copy) and the pure
> `tempestroid` from `../tempestroid` (excluding `renderers/qt`). The APK extracts
> the stdlib on **first launch**, so the first boot is slow (tens of seconds).

## 5. Run and capture

```bash
adb -s 0d474c147d75 shell am start -n org.tempestroid.host/.MainActivity
# wait for the interpreter to boot (~20 s the first time), then:
adb -s 0d474c147d75 exec-out screencap -p > shot.png
adb -s 0d474c147d75 logcat -d | grep -iE "tempestroid|python|FATAL"
```

With no `tempest_dev_url` and no bundled `tempest_app.py`, the Activity runs the
**built-in demo** (`MainActivity.DEVICE_DEMO`).

### Dev mode (LAN code-push)

```bash
adb reverse tcp:8765 tcp:8765
tempest serve examples/device_counter/app.py
adb shell am start -n org.tempestroid.host/.MainActivity \
  --es tempest_dev_url http://localhost:8765
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `adb start-server`/`devices` hangs | WSL mirrored networking — use the `nodaemon` background server (§3). |
| `vhci_hcd: urb->status -104` in `dmesg` | usbip connection reset — re-run `usbipd attach`, swap USB port/cable. |
| `INSTALL_FAILED_USER_RESTRICTED` | Enable **"Install via USB"** in Developer options (MIUI/HyperOS). |
| Gradle fails with an AGP error | Use the **wrapper 8.11.1** (`./gradlew`), not the global Gradle. |
| `_*` dir missing from the APK | AGP's default `ignoreAssetsPattern` drops `_*` dirs; already overridden in `app/build.gradle.kts`. |
| `usbipd` not recognized | usbipd-win not installed — see §1; reopen PowerShell after installing. |

---

## No physical hardware — headless x86_64 emulator (Trilho F7/F8)

A physical device on WSL is fragile (usbipd drops, MIUI needs toggles, the screen
locks). The recommended path to validate the native side **without hardware** is a
**headless x86_64 emulator**, which covers everything the device does — CPython
boot, JNI bridge, Compose renderer and native capabilities — and runs in CI.

!!! info "Preview-first"
    The **Qt simulator** (`make run` / `make dev`) is your instant UI-iteration
    view. The **emulator** is the real native-side verification. Iterate in Qt;
    only go to the emulator to confirm Compose/JNI/native — don't wait on the AVD
    for every screen change.

### Prerequisite: KVM

```bash
[ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM OK" || echo "no KVM"
```

Without `/dev/kvm` (CI without nested virtualization) the emulator is too slow —
use a **cloud device farm** (Firebase Test Lab / Genymotion SaaS / BrowserStack)
as a fallback. The F8 scripts detect a missing KVM and warn.

### 1. Provision the AVD (reproducible)

```bash
make provision-avd          # create the pinned AVD (idempotent; FORCE=1 recreates)
```

Installs the exact system image (`android-34`, `google_apis`, `x86_64`) and
creates the `pixel8_api34` AVD. Re-running is a no-op — the whole team gets the
**same** AVD.

### 2. Save the golden snapshot (fast boot)

```bash
make emulator-snapshot      # boot once (writable) and save the 'golden' snapshot
```

After this, `make emulator` **restores from the snapshot in seconds** (known-clean
state) instead of cold-booting. Re-run when the system image or host changes.

### 3. Boot + verify

```bash
make emulator               # fast boot from the 'golden' snapshot (falls back to cold boot)
make emulator-verify APP=examples/counter/app.py   # boot → stage x86 → x86 APK → install → serve → screenshot
VISUAL=1 make emulator-verify APP=examples/counter/app.py  # + visual regression against the versioned golden
```

`emulator-verify` does **real readiness gating** (`sys.boot_completed=1` + boot
animation stopped + `pm` responding) and **auto-recovers** a wedged AVD once
before giving up — every `adb` call is time-bounded (the F5 `device_loop.sh`
helpers), so a stuck emulator never hangs the harness.

### 4. Visual regression

`VISUAL=1` compares the captured screenshot against a versioned golden under
`docs/assets/emulator/golden/<example>.png` (default 2% tolerance, via
`toolchain/visual_regression.py` — Pillow). A missing golden is **created** on the
first run (baseline). It complements the Roborazzi JVM goldens (F7 camada B) and
the conformance suite (phase D): those pin the `Style` translation, this pins the
end-to-end on-emulator render.

### 5. Pool of N emulators in parallel (experimental)

```bash
make emulator-pool N=3      # shard the example gallery across 3 isolated instances
```

Each instance is **isolated** (own port/serial, `-read-only` from the golden
snapshot), so N emulators share the base image without corrupting each other's
state; a wedged one is recovered without dropping the others. Validation time
drops ~linearly with cores/RAM. **Experimental — not yet validated on a booting
emulator; validate end-to-end before relying on it in CI.**

### 6. Live mirroring (`scrcpy`)

```bash
make mirror                 # mirror the emulator/device in a host window (needs WSLg)
```

`scrcpy` shows and clicks the native side live. On WSL it needs **WSLg** (X). It
does not replace the `emulator-verify` screenshot — it's for interactive inspection.

### GPU robustness on WSL

The default is `-gpu swiftshader_indirect` (software render, stable headless). If
the screen comes up black/corrupted, try `-gpu guest` or `-gpu host` (the latter
needs WSLg). Separate gotcha from the desktop simulator: Qt on WSL needs
`QT_QPA_PLATFORM=xcb` (wayland backend bug) — emulator and simulator have distinct
GPU gotchas.

### Troubleshooting (emulator)

| Symptom | Cause / fix |
|---|---|
| `make emulator` cold-boots every time | No `golden` snapshot — run `make emulator-snapshot` once. |
| AVD never becomes ready | `emulator-verify` auto-recovers once; if it persists, `emulator -avd <AVD> -wipe-data` (destructive) and re-snapshot. |
| `adb` hangs under load | The `device_loop.sh` helpers time-bound every call; recover with `adb kill-server && adb start-server`. |
| snapshot save fails | The boot must be **writable** — `emulator-snapshot` uses `EMU_READONLY=0`; never save with `-read-only`. |
| no `/dev/kvm` | No acceleration — use a cloud farm; don't push the local emulator. |
