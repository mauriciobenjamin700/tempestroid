---
name: android-doctor
description: Validate the Android (Trilho B) build/run toolchain on this host before building or installing the android-host APK — Android SDK/NDK location, Gradle wrapper version, JDK, connected arm64 device, MIUI "Install via USB", and the staged CPython 3.14 + wheels. Use before `make apk`/`make install`/`make apk-install`/`tempest serve`, when device build/install fails, or when asked to "check the Android toolchain" / "run android-doctor".
---

# android-doctor

The Trilho B device path needs an Android SDK/NDK host + a connected arm64
device, and this host has known gotchas (SDK at `/usr/lib/android-sdk` not the
stale `ANDROID_HOME`; AGP 8.7 needs the bundled Gradle wrapper 8.11.1 not the
global Gradle 9.5; MIUI needs "Install via USB"). This skill checks all of them
*before* a build so failures are diagnosed up front, not mid-Gradle.

It is the Android counterpart of `framework-guard`: `framework-guard` validates
the pure-Python framework (Trilho A); `android-doctor` validates the device
toolchain (Trilho B).

## When to use

- Before `make apk` / `make install` / `make apk-install` / `make logcat`.
- Before `tempest serve <app>` (LAN code-push) or `tempest install`.
- When a device build/install fails (`INSTALL_FAILED_USER_RESTRICTED`, AGP/Gradle
  version errors, missing NDK, no device).
- When the user asks to "check the Android toolchain", "is the device ready?",
  or "run android-doctor".

## How to run

```bash
bash .claude/skills/android-doctor/check.sh
```

It reports a single PASS/FAIL summary over these checks:

1. **SDK root** — `ANDROID_SDK_ROOT` (or `/usr/lib/android-sdk` fallback) exists
   and holds `platform-tools/adb`. Warns if the stale `ANDROID_HOME` differs.
2. **NDK** — at least one NDK is present under `$SDK/ndk/` (native `libpython` +
   `libtempest_host` build needs it).
3. **JDK** — `java` on PATH (AGP 8.7 needs JDK 17+).
4. **Gradle wrapper** — `android-host/gradlew` exists and its
   `gradle-wrapper.properties` pins **8.11.1** (the global Gradle 9.5 is too new
   for AGP 8.7 — using it fails the build).
5. **Device** — `adb devices` lists exactly one device in `device` state (not
   `unauthorized`/`offline`); reports its ABI (`getprop ro.product.cpu.abi`) and
   warns if it isn't `arm64-v8a`.
6. **Staged runtime** — `toolchain/dist/python/arm64-v8a/` holds `libpython3.14.so`
   and `toolchain/dist/site-packages/` holds `pydantic` (run `make toolchain` if
   missing).

`--quick` skips the device/`adb` checks (host-only: SDK/NDK/JDK/Gradle/staging).

## Interpreting failures

- **SDK root missing** → `export ANDROID_SDK_ROOT=/usr/lib/android-sdk` (this
  host's real SDK; the env's default `ANDROID_HOME` is stale).
- **NDK missing** → install via `sdkmanager` or Android Studio; the native libs
  can't build without it.
- **Gradle wrapper wrong/absent** → never run the device build with the global
  `gradle`; always `cd android-host && ./gradlew …` (or `make apk`). The wrapper
  must stay pinned to 8.11.1 until AGP is upgraded.
- **No device / `unauthorized`** → plug in, accept the USB-debugging prompt; on
  MIUI also enable **Developer options → Install via USB** or `adb install`
  fails `INSTALL_FAILED_USER_RESTRICTED`.
- **Wrong ABI** → the host targets `arm64-v8a`; an x86_64 emulator needs the
  matching staged wheel/runtime.
- **Staging missing** → run `make toolchain` (fetch CPython 3.14 + build wheels +
  stage site-packages); needs the SDK/NDK above.

If no device is connected, this is expected in a bare WSL session — state that
the device half cannot be exercised here (matches the CLAUDE.md "Dual-renderer
device verification" rule). Report the exact failing output; do not summarize the
error away.
