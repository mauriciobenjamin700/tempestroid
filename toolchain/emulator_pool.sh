#!/usr/bin/env bash
# emulator_pool.sh — run the example gallery across N isolated emulators (F8).
#
# Booting one AVD validates the gallery serially; a pool of N instances shards
# the suite and cuts wall-clock ~linearly with cores/RAM. Each instance is
# ISOLATED: its own console port + serial, booted -read-only from the golden
# snapshot, so they share the base image without corrupting each other's state.
# A wedged instance is recovered independently (emu_recover) without dropping
# the others; everything is torn down at the end.
#
# !!! EXPERIMENTAL — written for the F8 reliability layer but NOT yet validated
# !!! on a booting emulator (the host's only AVD was owned by another session at
# !!! authoring time). Syntax-checked only. Validate end-to-end before relying
# !!! on it in CI. See docs/guia/dispositivo-wsl.md.
#
# Env knobs:
#   N           instance count            (default: min(4, nproc/2))
#   AVD         AVD name                  (default pixel8_api34)
#   SNAPSHOT    snapshot to restore       (default golden)
#   APPS        space-separated app list  (default: every examples/*/app.py)
#   READY_WAIT  per-instance boot timeout (default 180)
#
# Usage: bash toolchain/emulator_pool.sh           # default apps
#        N=3 APPS="examples/counter/app.py …" bash toolchain/emulator_pool.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
# shellcheck source=toolchain/device_loop.sh
. "$ROOT/toolchain/device_loop.sh"

AVD="${AVD:-pixel8_api34}"
SNAPSHOT="${SNAPSHOT:-golden}"
READY_WAIT="${READY_WAIT:-180}"
HOST="org.tempestroid.host"
SHOT_DIR="$ROOT/docs/assets/emulator/pool"
GOLDEN_DIR="$ROOT/docs/assets/emulator/golden"

# Pool size: bound by hardware (half the cores), capped at 4 unless overridden.
default_n=$(( $(nproc 2>/dev/null || echo 2) / 2 ))
[ "$default_n" -lt 1 ] && default_n=1
[ "$default_n" -gt 4 ] && default_n=4
N="${N:-$default_n}"

# App list: explicit APPS, else every example with an app.py.
if [ -n "${APPS:-}" ]; then
    read -r -a apps <<<"$APPS"
else
    mapfile -t apps < <(find "$ROOT/examples" -mindepth 2 -maxdepth 2 -name app.py | sort)
fi
[ "${#apps[@]}" -gt 0 ] || { echo "POOL: no apps to run" >&2; exit 2; }

kvm_available || echo "==> WARNING: /dev/kvm not usable — N>1 will thrash. Consider a cloud farm."

echo "==> booting pool of $N instance(s) from snapshot '$SNAPSHOT'"
serials=()
ports=()
for i in $(seq 0 $((N - 1))); do
    port=$((5554 + i * 2))
    serial="emulator-$port"
    serials+=("$serial")
    ports+=("$port")
    echo "    [$((i + 1))/$N] booting $serial (port $port)"
    emu_boot "$AVD" "$serial" "$port" "$SNAPSHOT"
done

# Teardown every instance on exit (clean, even on error/interrupt).
teardown() {
    for s in "${serials[@]}"; do emu_stop "$s"; done
}
trap teardown EXIT

echo "==> waiting for readiness + installing host on each instance"
ready_serials=()
for idx in "${!serials[@]}"; do
    serial="${serials[$idx]}"
    if ! emu_wait_ready "$serial" "$READY_WAIT"; then
        echo "    $serial not ready — recovering"
        emu_recover "$AVD" "$serial" "${ports[$idx]}" || { echo "    $serial unrecoverable — skipping"; continue; }
    fi
    adbq -s "$serial" install -r "$ROOT/android-host/app/build/outputs/apk/debug/app-debug.apk" \
        >/dev/null 2>&1 || { echo "    $serial install failed — skipping"; continue; }
    ready_serials+=("$serial")
done
[ "${#ready_serials[@]}" -gt 0 ] || { echo "POOL: no ready instances" >&2; exit 3; }
echo "    ready instances: ${ready_serials[*]}"

mkdir -p "$SHOT_DIR"
# verify_one <serial> <app.py> — serve the app to one instance, screenshot, and
# compare to its golden. Echoes "PASS <name>" / "FAIL <name>".
verify_one() {
    local serial="$1" app="$2" name shot
    name="$(basename "$(dirname "$app")")"
    shot="$SHOT_DIR/$name.png"
    adbq -s "$serial" shell pm grant "$HOST" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true
    adbq -s "$serial" shell am force-stop "$HOST" >/dev/null 2>&1 || true
    ANDROID_SERIAL="$serial" setsid uv run --project "$ROOT" tempest serve "$app" \
        >"/tmp/pool-serve-$serial-$name.log" 2>&1 &
    local spid=$!
    local waited=0
    while [ "$waited" -lt 50 ]; do
        if adbq -s "$serial" logcat -d -t 400 2>/dev/null | grep -q "pushed app"; then break; fi
        sleep 3; waited=$((waited + 3))
    done
    sleep 6
    adbq -s "$serial" exec-out screencap -p >"$shot" 2>/dev/null
    kill -- "-$spid" >/dev/null 2>&1 || true
    if [ ! -s "$shot" ]; then echo "FAIL $name (no screenshot)"; return; fi
    if uv run --project "$ROOT" python "$ROOT/toolchain/visual_regression.py" \
        "$shot" "$GOLDEN_DIR/$name.png" >/dev/null 2>&1; then
        echo "PASS $name"
    else
        echo "FAIL $name (visual regression)"
    fi
}

echo "==> sharding ${#apps[@]} app(s) across ${#ready_serials[@]} instance(s)"
results="$(mktemp)"
pids=()
for idx in "${!apps[@]}"; do
    serial="${ready_serials[$((idx % ${#ready_serials[@]}))]}"
    ( verify_one "$serial" "${apps[$idx]}" >>"$results" ) &
    pids+=($!)
    # Keep at most one app in flight per instance (serial reuse) — wait in waves.
    if [ $(((idx + 1) % ${#ready_serials[@]})) -eq 0 ]; then
        for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
        pids=()
    fi
done
for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done

echo
echo "==> POOL RESULTS"
sort "$results"
fails=$(grep -c '^FAIL' "$results" 2>/dev/null || echo 0)
rm -f "$results"
echo "  instances=${#ready_serials[@]}  apps=${#apps[@]}  fails=$fails"
[ "$fails" -eq 0 ] && echo "EMULATOR-POOL: PASS" || { echo "EMULATOR-POOL: FAIL"; exit 1; }
