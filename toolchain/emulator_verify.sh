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
# shellcheck source=toolchain/device_loop.sh
. "$ROOT/toolchain/device_loop.sh"
APP="${1:-examples/counter/app.py}"
AVD="${AVD:-pixel8_api34}"
EMU_SERIAL="${EMU_SERIAL:-emulator-5554}"
EMU_PORT="${EMU_PORT:-5554}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_SDK_ROOT
EMU_APK="$ROOT/android-host/app/build/outputs/apk/debug/app-debug.apk"
SHOT_DIR="$ROOT/docs/assets/emulator"
SHOT="$SHOT_DIR/verify.png"
GOLDEN_DIR="$ROOT/docs/assets/emulator/golden"
BOOT_WAIT="${TEMPEST_EMU_BOOT_WAIT:-30}"
READY_WAIT="${TEMPEST_EMU_READY_WAIT:-300}"
# Wait for the app to actually MOUNT before the screenshot (code-push 'pushed
# app' marker + host owns the foreground), not a blind sleep — a blind sleep
# screenshots a still-booting blank screen and false-greens. SETTLE lets Compose
# paint the first frame after the host is foreground.
MOUNT_WAIT="${TEMPEST_EMU_MOUNT_WAIT:-120}"
SETTLE="${TEMPEST_EMU_SETTLE:-8}"
HOST_PKG="org.tempestroid.host"
# VISUAL=1 compares the final screenshot to a versioned golden (F8); a missing
# golden is created (baseline). Off by default so the legacy flow is unchanged.
VISUAL="${VISUAL:-0}"

adb_emu() { adb -s "$EMU_SERIAL" "$@"; }

fail() { echo "EMULATOR-VERIFY: FAIL — $*" >&2; exit 1; }

echo "==> [1/6] ensure emulator $EMU_SERIAL is up (AVD=$AVD)"
make -C "$ROOT" emulator AVD="$AVD" EMU_SERIAL="$EMU_SERIAL" ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
# Gate on genuine readiness (not just wait-for-device, which races the slow
# swiftshader path). Recover once if the AVD is wedged before giving up.
if ! emu_wait_ready "$EMU_SERIAL" "$READY_WAIT"; then
    echo "    not ready — attempting one recovery"
    emu_recover "$AVD" "$EMU_SERIAL" "$EMU_PORT" || fail "emulator $EMU_SERIAL never became ready"
fi

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
# Pre-grant POST_NOTIFICATIONS: on API 33+ a fresh install pops a runtime
# permission dialog (GrantPermissionsActivity) that covers the host — the host
# then never owns the foreground and the mount gate (rightly) fails. Granting it
# up front (the host declares it for the notify capability) keeps the dialog from
# stealing focus. Best-effort: a failure here must not abort the run.
adb_emu shell pm grant "$HOST_PKG" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true

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
echo "    serve pid=$serve_pid log=$serve_log"
# Wait for a real mount, not a blind sleep: (1) the code-push pushed the bundle
# ('pushed app' in logcat), then (2) the host owns the foreground. A blind sleep
# screenshots a still-booting blank screen and reports a false PASS.
echo "    waiting for mount (up to ${MOUNT_WAIT}s): code-push push + host foreground"
host_is_foreground() {
    adb_emu shell dumpsys activity activities 2>/dev/null \
        | grep -E "mResumedActivity|topResumedActivity|ResumedActivity" \
        | grep -q "$HOST_PKG"
}
waited=0
pushed=0
while [ "$waited" -lt "$MOUNT_WAIT" ]; do
    if [ "$pushed" = "0" ] && adb_emu logcat -d -t 600 2>/dev/null | grep -q "pushed app"; then
        pushed=1
        echo "    code-push pushed the app (${waited}s)"
    fi
    if [ "$pushed" = "1" ] && host_is_foreground; then
        echo "    host is foreground (${waited}s) — settling ${SETTLE}s for first paint"
        break
    fi
    sleep 3
    waited=$((waited + 3))
done
[ "$pushed" = "1" ] || fail "code-push never pushed the app within ${MOUNT_WAIT}s (serve log: $serve_log)"
host_is_foreground || fail "host never reached the foreground — app failed to mount (serve log: $serve_log)"
sleep "$SETTLE"

echo "==> [6/6] screenshot → $SHOT"
mkdir -p "$SHOT_DIR"
adb_emu exec-out screencap -p > "$SHOT" || fail "screencap failed"
[ -s "$SHOT" ] || fail "screenshot is empty"
# Final guard: the host must STILL own the foreground at capture time, else the
# screenshot is the launcher (the blank-screen false-green this replaces).
host_is_foreground || fail "host left the foreground before capture — screenshot is not the app"
echo "    saved $SHOT ($(du -h "$SHOT" | cut -f1))"

echo "==> scanning logcat for Python tracebacks"
logdump="$(adb_emu logcat -d -s tempest:V python:V AndroidRuntime:E 2>/dev/null || true)"
if echo "$logdump" | grep -qE 'Traceback \(most recent call last\)|FATAL EXCEPTION'; then
    echo "$logdump" | grep -E 'Traceback|Error|Exception' | tail -20 >&2
    fail "Python traceback / fatal exception in logcat"
fi

if [ "$VISUAL" = "1" ]; then
    app_name="$(basename "$(dirname "$APP")")"
    golden="$GOLDEN_DIR/$app_name.png"
    echo "==> visual regression vs $golden"
    if ! uv run --project "$ROOT" python "$ROOT/toolchain/visual_regression.py" \
        "$SHOT" "$golden" --tolerance "${VISUAL_TOLERANCE:-0.02}"; then
        fail "visual regression against golden $golden"
    fi
fi

echo
echo "EMULATOR-VERIFY: PASS"
echo "  app=$APP  emulator=$EMU_SERIAL  apk=$EMU_APK"
echo "  screenshot=$SHOT"
echo "  (verify the rendered UI in the screenshot; tap the '+' with:"
echo "     adb -s $EMU_SERIAL shell input tap 468 372 && adb -s $EMU_SERIAL exec-out screencap -p > $SHOT_DIR/verify-after-tap.png)"
