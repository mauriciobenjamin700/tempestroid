#!/usr/bin/env bash
# capture_gif.sh <app.py> [out.gif] — capture an ANIMATED tempestroid example as
# a looped .gif (a static .png can't show the animation).
#
# Bursts ~$FRAMES on-device screencaps at $INTERVAL after the app mounts, then
# assembles them with toolchain/frames_to_gif.py (Pillow). Targets whatever adb
# device $ANDROID_SERIAL selects (set it to the emulator for the hardware-free
# path). Reuses the F5 device_loop helpers so every adb call is time-bounded.
#
# Env: FRAMES (default 12), INTERVAL secs (default 0.25), MOUNT_WAIT (default 50).
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
# shellcheck source=toolchain/device_loop.sh
. "$(dirname "${BASH_SOURCE[0]}")/device_loop.sh"

APP="${1:?usage: capture_gif.sh <app.py> [out.gif]}"
NAME="$(basename "$(dirname "$APP")")"
OUT="${2:-docs/assets/examples/$NAME.gif}"
FRAMES="${FRAMES:-12}"
INTERVAL="${INTERVAL:-0.25}"
MOUNT_WAIT="${MOUNT_WAIT:-50}"
HOST="org.tempestroid.host"

device_alive || { abort_clean "" "no device — connect/boot the emulator first"; exit 3; }

adbq shell pm grant "$HOST" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true
adbq shell am force-stop "$HOST" >/dev/null 2>&1
adbq logcat -c >/dev/null 2>&1

setsid uv run tempest serve "$APP" >"/tmp/serve_gif_$NAME.log" 2>&1 &
spid=$!
trap 'kill -- "-$spid" >/dev/null 2>&1 || true' EXIT

echo "==> waiting for $NAME to mount (up to ${MOUNT_WAIT}s)"
waited=0
while [ "$waited" -lt "$MOUNT_WAIT" ]; do
    if adbq logcat -d -t 400 2>/dev/null | grep -q "pushed app"; then break; fi
    device_alive || { abort_clean "$spid" "device dropped while waiting for $NAME"; exit 3; }
    sleep 3; waited=$((waited + 3))
done
sleep 6  # settle: let Compose paint the first frame

# Optional trigger: many examples are static at rest (a stopwatch needs "start",
# an animation needs a toggle). TAP_X/TAP_Y taps once before the burst to kick
# the animation so the frames actually differ.
if [ -n "${TAP_X:-}" ] && [ -n "${TAP_Y:-}" ]; then
    echo "==> tapping ($TAP_X,$TAP_Y) to trigger the animation"
    adbq shell input tap "$TAP_X" "$TAP_Y" >/dev/null 2>&1 || true
    sleep 1
fi

tmp="$(mktemp -d)"
echo "==> capturing $FRAMES frames every ${INTERVAL}s"
for i in $(seq -w 1 "$FRAMES"); do
    adbq exec-out screencap -p > "$tmp/f$i.png" 2>/dev/null
    sleep "$INTERVAL"
done

mkdir -p "$(dirname "$OUT")"
uv run python toolchain/frames_to_gif.py "$tmp" "$OUT"
rm -rf "$tmp"
