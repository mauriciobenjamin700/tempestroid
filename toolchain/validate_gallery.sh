#!/usr/bin/env bash
# Drive every example through the on-device code-push path and screenshot it.
# Not a release artifact — the one-shot device-validation harness (Trilho F5).
#
# Per app: force-stop the host (so the next launch is a COLD fetch of the new
# app, not a foregrounding of the previous one), start `tempest serve` (which
# re-launches the host in dev mode pointing at the fresh server), then wait for
# a STABLE frame (two identical screencaps after a warmup) before capturing.
#
# Hardened against USB drop (the 2026-06-13 incident): every adb call is
# time-bounded via `adbq`, a dropped device is detected and aborts the run
# cleanly (no wedged adb), and results are CHECKPOINTED per app so a re-run
# RESUMES from where it stopped instead of redoing the green apps.
#
# serve is started under its own process group (setsid) and killed by group id
# — NEVER `pkill -f`, which would also match this script's own command line.
#
# Env knobs:
#   FRESH=1        ignore the existing checkpoint and re-validate everything.
#   ADB_TIMEOUT=N  per-adb-call timeout in seconds (default 20; see device_loop).
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
export ANDROID_SDK_ROOT=/usr/lib/android-sdk

# shellcheck source=toolchain/device_loop.sh
. "$(dirname "${BASH_SOURCE[0]}")/device_loop.sh"

OUT="docs/assets/examples"
RESULTS="/tmp/gallery_results.txt"
HOST="org.tempestroid.host"
# Per-app timing. Defaults suit the (slow) swiftshader emulator; a fast physical
# device can shrink them (MOUNT_WAIT=20 SETTLE=3 …) for a quicker sweep.
MOUNT_WAIT="${MOUNT_WAIT:-50}"   # max seconds to wait for the "pushed app" mount marker
SETTLE="${SETTLE:-6}"            # seconds to let Compose paint after the push
FG_WAIT="${FG_WAIT:-20}"         # max seconds to wait for the host to be foreground
LOGTAIL="${LOGTAIL:-400}"        # logcat -t window (lighter than a full -d dump)
mkdir -p "$OUT"
# Checkpoint file: keep it across runs so we can resume; FRESH=1 starts over.
if [ "${FRESH:-0}" = "1" ]; then : > "$RESULTS"; fi
touch "$RESULTS"

LAST_SPID=""

# already_pass <name> — true if this app already has a PASS line (resume skip).
already_pass() {
    grep -q "^PASS   $1 " "$RESULTS" 2>/dev/null
}

# Guard: bail out before we even start if the device is not reachable.
if ! device_alive; then
    abort_clean "" "no device before start — connect/authorize the device first"
    exit 3
fi

adbq reverse tcp:8765 tcp:8765 >/dev/null 2>&1 || true

# Pre-grant POST_NOTIFICATIONS so the first-launch runtime permission dialog never
# overlays a captured frame (Android 13+). Harmless if the perm/host is absent.
adbq shell pm grant "$HOST" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true

# validate <name> <path> — returns 0 on PASS/FAIL recorded, 1 if the device
# dropped mid-app (caller aborts the whole run).
validate() {
    local name="$1" path="$2"
    echo "==> $name ($path)"
    adbq shell am force-stop "$HOST" >/dev/null 2>&1
    sleep 2
    adbq logcat -c >/dev/null 2>&1
    setsid uv run tempest serve "$path" >"/tmp/serve_$name.log" 2>&1 &
    local spid=$!
    LAST_SPID="$spid"

    # Wait for the app to actually MOUNT, not merely for a "stable" frame: a slow
    # target (the swiftshader emulator boots CPython in ~15-30s) shows the launcher
    # meanwhile, and the launcher is itself a stable frame. Poll logcat (a light
    # `-t $LOGTAIL` window, NOT a full `-d` buffer dump — the heavy dumps under
    # rapid cycling were wedging the emulator's adb channel) for the push marker.
    local mounted=0 waited=0
    while [ "$waited" -lt "$MOUNT_WAIT" ]; do
        if adbq logcat -d -t "$LOGTAIL" 2>/dev/null | grep -q "pushed app"; then mounted=1; break; fi
        if ! device_alive; then
            kill -- "-$spid" >/dev/null 2>&1 || true
            echo "ABORT  $name  usb-drop (waiting mount)" >> "$RESULTS"
            return 1
        fi
        sleep 3; waited=$((waited + 3))
    done
    # settle: let Compose paint the first real frame after the push.
    sleep "$SETTLE"
    # Foreground-gate: confirm the host owns the resumed activity before the
    # screenshot. If it never foregrounds (booting / crashed back to launcher),
    # the capture would be the launcher — we record that as a FAIL, never a PASS.
    local fg=0 fgwaited=0
    while [ "$fgwaited" -lt "$FG_WAIT" ]; do
        if host_foreground "$HOST"; then fg=1; break; fi
        if ! device_alive; then
            kill -- "-$spid" >/dev/null 2>&1 || true
            echo "ABORT  $name  usb-drop (waiting foreground)" >> "$RESULTS"
            return 1
        fi
        sleep 3; fgwaited=$((fgwaited + 3))
    done
    # ONE screencap (the old 8-iteration stable loop was a heavy adb hot-spot).
    adbq exec-out screencap -p > "$OUT/$name.png" 2>/dev/null

    local err md5
    # `|| true`: a clean logcat means grep exits 1; without errexit that is
    # already harmless (err="" → PASS branch), but make the intent explicit so a
    # future `set -e` cannot turn "no errors found" into a script abort.
    err=$(adbq logcat -d -t "$LOGTAIL" 2>/dev/null | grep -iE 'Traceback|ModuleNotFoundError|ImportError|dev client error' | head -2 | tr '\n' '|') || true
    md5="$(md5sum "$OUT/$name.png" 2>/dev/null | cut -d' ' -f1)"
    if [ -n "$err" ]; then
        echo "FAIL   $name  mounted=$mounted fg=$fg  md5=$md5  :: $err" >> "$RESULTS"
    elif [ "$mounted" -eq 0 ]; then
        echo "FAIL   $name  mounted=0 (no 'pushed app' in ${MOUNT_WAIT}s)  md5=$md5" >> "$RESULTS"
    elif [ "$fg" -eq 0 ]; then
        echo "FAIL   $name  fg=0 (host not foreground in ${FG_WAIT}s — capture is the launcher)  md5=$md5" >> "$RESULTS"
    else
        echo "PASS   $name  mounted=1 fg=1  md5=$md5" >> "$RESULTS"
    fi
    # kill the serve process GROUP (setsid leader); no pattern matching.
    kill -- "-$spid" >/dev/null 2>&1 || true
    LAST_SPID=""
    sleep 1
    return 0
}

for d in examples/*/; do
    name="$(basename "$d")"
    path="$d/app.py"
    [ -f "$path" ] || path="$d/main.py"
    [ -f "$path" ] || continue

    if already_pass "$name"; then
        echo "==> $name (skip — already PASS, resuming)"
        continue
    fi

    # Pre-check: a drop between apps is the common case — catch it cheaply.
    if ! device_alive; then
        echo "ABORT  $name  usb-drop (pre-check)" >> "$RESULTS"
        abort_clean "$LAST_SPID" "device dropped before '$name'"
        exit 3
    fi

    if ! validate "$name" "$path"; then
        abort_clean "$LAST_SPID" "device dropped during '$name'"
        exit 3
    fi
done

echo "==> done"
cat "$RESULTS"
echo "=== distinct screenshot md5 (want ~24) ==="
awk -F'md5=' '/md5=/{print $2}' "$RESULTS" | awk '{print $1}' | sort -u | wc -l
