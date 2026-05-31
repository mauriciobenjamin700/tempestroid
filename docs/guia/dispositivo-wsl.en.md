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
