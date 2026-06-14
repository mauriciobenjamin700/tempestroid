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
