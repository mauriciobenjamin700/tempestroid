#!/usr/bin/env bash
# emulator_verify.sh — end-to-end F7 verification on a HEADLESS x86_64 emulator,
# without ever touching a physical device.
#
# Chain: ensure emulator up → stage x86_64 runtime → build x86_64 APK → install
# on the emulator → `tempest serve` the app at the emulator → wait for CPython
# boot + code-push → screenshot → scan logcat for tracebacks → report PASS/FAIL.
#
# Every adb/serve step targets the emulator EXPLICITLY (-s $EMU_SERIAL /
# ANDROID_SERIAL) because a physical device may ALSO be connected.
#
# Usage: bash toolchain/emulator_verify.sh [APP]   (default examples/counter/app.py)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-examples/counter/app.py}"
AVD="${AVD:-pixel8_api34}"
EMU_SERIAL="${EMU_SERIAL:-emulator-5554}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_SDK_ROOT
EMU_APK="$ROOT/android-host/app/build/outputs/apk/debug/app-debug.apk"
SHOT_DIR="$ROOT/docs/assets/emulator"
SHOT="$SHOT_DIR/verify.png"
BOOT_WAIT="${TEMPEST_EMU_BOOT_WAIT:-30}"

adb_emu() { adb -s "$EMU_SERIAL" "$@"; }

fail() { echo "EMULATOR-VERIFY: FAIL — $*" >&2; exit 1; }

echo "==> [1/6] ensure emulator $EMU_SERIAL is up (AVD=$AVD)"
make -C "$ROOT" emulator AVD="$AVD" EMU_SERIAL="$EMU_SERIAL" ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
adb_emu wait-for-device

echo "==> [2/6] stage x86_64 CPython runtime + site-packages"
bash "$ROOT/toolchain/stage_emulator_runtime.sh"

echo "==> [3/6] build x86_64 APK"
make -C "$ROOT" apk-x86 ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
[ -f "$EMU_APK" ] || fail "APK not produced at $EMU_APK"
echo "    APK: $EMU_APK ($(du -h "$EMU_APK" | cut -f1))"
# Confirm it's an x86_64-only APK (no arm64 libs leaked in).
if unzip -l "$EMU_APK" | grep -q 'lib/arm64-v8a/'; then
    fail "APK contains lib/arm64-v8a — expected x86_64-only"
fi

echo "==> [4/6] install on $EMU_SERIAL"
adb_emu install -r "$EMU_APK" || fail "adb install failed"

echo "==> [5/6] tempest serve $APP at the emulator (background)"
adb_emu logcat -c || true
# Serve pinned to the emulator via ANDROID_SERIAL so adb reverse + launch hit it,
# never the physical device. Backgrounded under setsid; killed on exit.
serve_log="$(mktemp)"
ANDROID_SERIAL="$EMU_SERIAL" setsid uv run --project "$ROOT" tempest serve "$APP" \
    >"$serve_log" 2>&1 &
serve_pid=$!
cleanup() { kill -- "-$serve_pid" 2>/dev/null || kill "$serve_pid" 2>/dev/null || true; }
trap cleanup EXIT
echo "    serve pid=$serve_pid log=$serve_log; waiting ${BOOT_WAIT}s for CPython boot + push"
sleep "$BOOT_WAIT"

echo "==> [6/6] screenshot → $SHOT"
mkdir -p "$SHOT_DIR"
adb_emu exec-out screencap -p > "$SHOT" || fail "screencap failed"
[ -s "$SHOT" ] || fail "screenshot is empty"
echo "    saved $SHOT ($(du -h "$SHOT" | cut -f1))"

echo "==> scanning logcat for Python tracebacks"
logdump="$(adb_emu logcat -d -s tempest:V python:V AndroidRuntime:E 2>/dev/null || true)"
if echo "$logdump" | grep -qE 'Traceback \(most recent call last\)|FATAL EXCEPTION'; then
    echo "$logdump" | grep -E 'Traceback|Error|Exception' | tail -20 >&2
    fail "Python traceback / fatal exception in logcat"
fi

echo
echo "EMULATOR-VERIFY: PASS"
echo "  app=$APP  emulator=$EMU_SERIAL  apk=$EMU_APK"
echo "  screenshot=$SHOT"
echo "  (verify the rendered UI in the screenshot; tap the '+' with:"
echo "     adb -s $EMU_SERIAL shell input tap 468 372 && adb -s $EMU_SERIAL exec-out screencap -p > $SHOT_DIR/verify-after-tap.png)"
