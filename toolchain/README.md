# toolchain/ — Trilho B build scripts

Scripts to produce the two artifacts the Android host needs:

1. **CPython 3.14 for `aarch64-linux-android`** (official binary release, or a
   custom cross-build) — see `00_fetch_cpython.sh`.
2. **Native wheels** (`pydantic-core` + friends) cross-compiled with
   **cibuildwheel** — see `01_build_wheels.sh`.

> These require an **Android SDK + NDK r27** on a **Linux x86_64 or macOS** host.
> They do **not** run in a bare WSL session without that toolchain installed.
> Rationale, versions, and sources: [`../docs/research/android-runbook.md`](../docs/research/android-runbook.md).

## Prerequisites

```bash
# Android SDK command-line tools at $ANDROID_HOME/cmdline-tools/latest
# NDK r27 (27.3.13750724) — android.py / cibuildwheel can install it via sdkmanager
export ANDROID_HOME=$HOME/Android/Sdk
export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.3.13750724
# Rust target for pydantic-core
rustup target add aarch64-linux-android
cargo install cargo-ndk
# uv (build frontend; pip is NOT supported for Android wheels)
```

Then source the shared env and run the steps in order:

```bash
source toolchain/env.sh
toolchain/00_fetch_cpython.sh        # → toolchain/dist/python/<abi>/...
toolchain/01_build_wheels.sh         # → toolchain/dist/wheels/*.whl
```

The Gradle host (`../android-host`) consumes `toolchain/dist/`.
