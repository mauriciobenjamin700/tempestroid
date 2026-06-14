#!/usr/bin/env bash
# device_loop.sh — shared helpers for the on-device validation loop (Trilho F5).
#
# The on-device validation path is the bottleneck of the stabilization track:
# F2 (native caps), the release-apk/icon device-verify and the E8/E9 leftovers
# all depend on a device loop that does not hang. It used to: every `adb` call
# was raw, so when the device dropped off USB (common on WSL/usbipd) a
# `screencap` would block forever, the harness hung for ~25 min and left the adb
# server wedged. These helpers make every adb call time-bounded, detect a USB
# drop, and abort cleanly so a re-run can resume.
#
# Source this from a harness:  . "$(dirname "$0")/device_loop.sh"
# Tunables (env): ADB_TIMEOUT (per-call seconds, default 20), ADB (binary path).

# Resolve the adb binary the same way android-doctor does: prefer the real SDK
# under /usr/lib/android-sdk over a possibly-stale one on PATH.
: "${ADB_TIMEOUT:=20}"
if [ -z "${ADB:-}" ]; then
    if [ -x "/usr/lib/android-sdk/platform-tools/adb" ]; then
        ADB="/usr/lib/android-sdk/platform-tools/adb"
    else
        ADB="adb"
    fi
fi

# adbq — every adb call, time-bounded. A wedged adb returns 124 (timeout's
# exit code) instead of hanging the whole harness forever.
adbq() {
    timeout "${ADB_TIMEOUT}" "$ADB" "$@"
}

# device_alive — true iff exactly the adb layer reports a device in 'device'
# state. Returns non-zero (and never hangs) when the device dropped off USB,
# went offline/unauthorized, or the adb server itself is wedged.
device_alive() {
    local state
    state="$(adbq get-state 2>/dev/null | tr -d '\r')"
    [ "$state" = "device" ]
}

# cap_stable_md5 — md5 of a fresh screencap, or EMPTY when the capture produced
# no bytes (adb timed out / device gone). Returning empty (instead of the md5 of
# a zero-byte stream, which is a constant) keeps the "stable frame" loop from
# mistaking a dead device for a steady screen.
cap_stable_md5() {
    local f md5
    f="$(mktemp)"
    adbq exec-out screencap -p >"$f" 2>/dev/null
    if [ -s "$f" ]; then
        md5="$(md5sum "$f" | cut -d' ' -f1)"
        printf '%s' "$md5"
    fi
    rm -f "$f"
}

# host_foreground <package> — true iff <package> owns the resumed (foreground)
# activity. Gates captures so a screenshot is never the launcher sitting behind a
# still-booting / crashed-back app (the slow swiftshader emulator failure mode).
host_foreground() {
    local pkg="$1"
    adbq shell dumpsys activity activities 2>/dev/null \
        | grep -E "mResumedActivity|topResumedActivity|ResumedActivity" \
        | grep -q "$pkg"
}

# abort_clean <serve_pgid> <reason> — kill the serve process GROUP (setsid
# leader; never pattern-match, which would also match the harness itself),
# reset the (possibly wedged) adb server, and print a recovery hint. Safe to
# call with an empty pgid.
abort_clean() {
    local pgid="${1:-}" reason="${2:-aborted}"
    if [ -n "$pgid" ]; then
        kill -- "-$pgid" >/dev/null 2>&1 || true
    fi
    timeout 15 "$ADB" kill-server >/dev/null 2>&1 || true
    echo "ABORT  $reason"
    echo "       Recover: re-attach the device to WSL on Windows (PowerShell admin):"
    echo "         usbipd list                       # find the BUSID"
    echo "         usbipd attach --wsl --busid <ID>  # re-bind to WSL"
    echo "       then unlock the screen and re-run this harness — it resumes from the checkpoint."
}

# ---------------------------------------------------------------------------
# Emulator helpers (Trilho F8) — reliability layer over the headless x86_64 AVD
# the F7 target proved out. They make booting deterministic (snapshot), gate on
# real readiness (not just boot_completed), and auto-recover a wedged AVD —
# every adb call is still time-bounded via adbq, so a stuck emulator can never
# hang the harness. All are serial-scoped so a pool of AVDs can run in parallel.
# ---------------------------------------------------------------------------

# kvm_available — true iff /dev/kvm is usable (hardware-accelerated emulation).
# When false, a headless AVD is impractically slow and the caller should fall
# back to a cloud device farm (documented in docs/guia/dispositivo-wsl.md).
kvm_available() {
    [ -r /dev/kvm ] && [ -w /dev/kvm ]
}

# emu_online <serial> — true iff the adb layer reports <serial> in 'device'
# state. Never hangs (adbq is time-bounded); false when the AVD is gone/booting.
emu_online() {
    local serial="$1" state
    state="$(adbq -s "$serial" get-state 2>/dev/null | tr -d '\r')"
    [ "$state" = "device" ]
}

# emu_wait_ready <serial> <timeout_s> — block until the AVD is genuinely usable:
# sys.boot_completed=1 AND the boot animation stopped AND the package manager
# answers. Polling just boot_completed races the slow swiftshader path (install
# then fails "device offline"). Returns non-zero on timeout (never hangs).
emu_wait_ready() {
    local serial="$1" timeout_s="${2:-120}" waited=0
    while [ "$waited" -lt "$timeout_s" ]; do
        if [ "$(adbq -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] \
            && [ "$(adbq -s "$serial" shell getprop init.svc.bootanim 2>/dev/null | tr -d '\r')" = "stopped" ] \
            && adbq -s "$serial" shell pm path android >/dev/null 2>&1; then
            return 0
        fi
        sleep 3
        waited=$((waited + 3))
    done
    return 1
}

# emu_boot <avd> <serial> <port> [snapshot] — launch a headless AVD in the
# background. With a snapshot name it restores from it (boot in seconds, clean
# known state); without, it cold-boots (-no-snapshot). Each instance gets its
# own console port so a pool stays isolated. Logs to /tmp/tempest-emu-<port>.log.
#
# EMU_READONLY (env, default 1): boot -read-only so a pool of instances can
# share one AVD without locking. Set EMU_READONLY=0 to boot writable — required
# to SAVE a snapshot (the emulator refuses snapshot save in read-only mode).
emu_boot() {
    local avd="$1" serial="$2" port="${3:-5554}" snapshot="${4:-}"
    local emu="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}/emulator/emulator"
    local snap_args="-no-snapshot"
    if [ -n "$snapshot" ]; then
        snap_args="-snapshot $snapshot"
    fi
    local ro_args="-read-only"
    if [ "${EMU_READONLY:-1}" = "0" ]; then
        ro_args=""
    fi
    # shellcheck disable=SC2086
    setsid "$emu" -avd "$avd" -port "$port" \
        -no-window -no-audio -no-boot-anim \
        -gpu swiftshader_indirect $snap_args $ro_args \
        >"/tmp/tempest-emu-$port.log" 2>&1 &
    adbq -s "$serial" wait-for-device >/dev/null 2>&1 || true
}

# emu_stop <serial> — ask the emulator console to quit (clean), time-bounded.
emu_stop() {
    local serial="$1"
    adbq -s "$serial" emu kill >/dev/null 2>&1 || true
}

# emu_recover <avd> <serial> <port> [snapshot] — recover a wedged AVD: stop it,
# reset a possibly-wedged adb server, and cold-boot fresh. A snapshot that fails
# to restore is bypassed (cold-boot). As a last resort the caller wipes data
# (`emulator -avd <avd> -wipe-data`) — destructive, so left manual + documented.
emu_recover() {
    local avd="$1" serial="$2" port="${3:-5554}"
    echo "==> recovering wedged emulator $serial (cold boot)"
    emu_stop "$serial"
    timeout 15 "$ADB" kill-server >/dev/null 2>&1 || true
    timeout 15 "$ADB" start-server >/dev/null 2>&1 || true
    emu_boot "$avd" "$serial" "$port" ""
    emu_wait_ready "$serial" 180
}
