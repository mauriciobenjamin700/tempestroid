#!/usr/bin/env bash
# Diagnostic: does ONE serve session hot-reload when the watched file changes?
# Hardened (Trilho F5): adb calls are time-bounded via `adbq` and a USB drop
# aborts cleanly instead of hanging.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export ANDROID_SDK_ROOT=/usr/lib/android-sdk PYTHONUNBUFFERED=1

# shellcheck source=toolchain/device_loop.sh
. "$(dirname "${BASH_SOURCE[0]}")/device_loop.sh"

WATCH=/tmp/gapp.py
LOG=/tmp/serve_diag.log
HOST=org.tempestroid.host

if ! device_alive; then
    abort_clean "" "no device before start — connect/authorize the device first"
    exit 3
fi

cp examples/counter/app.py "$WATCH"
adbq shell am force-stop "$HOST" >/dev/null 2>&1
sleep 2
adbq logcat -c >/dev/null 2>&1

setsid uv run tempest serve "$WATCH" >"$LOG" 2>&1 &
spid=$!
echo "serve pgid=$spid; waiting for first mount (counter)..."
sleep 14
adbq exec-out screencap -p > /tmp/diag_1_counter.png 2>/dev/null
echo "shot1 (expect counter) saved"

echo "=== switching watched file to CALCULATOR ==="
cp examples/calculator/app.py "$WATCH"
touch "$WATCH"
sleep 12
adbq exec-out screencap -p > /tmp/diag_2_calc.png 2>/dev/null
echo "shot2 (expect calculator) saved"

echo "=== serve log ==="
cat "$LOG"
echo "=== device logcat (tempest/push/error) ==="
adbq logcat -d 2>/dev/null | grep -iE 'tempest|pushed|Traceback|No module|dev client|hot' | tail -20

kill -- "-$spid" >/dev/null 2>&1 || true
echo "done"
