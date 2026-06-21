#!/usr/bin/env bash
# emulator_snapshot.sh — capture the "golden" boot snapshot of the AVD (F8).
#
# Cold-booting the AVD on every run is slow (~minutes) and non-deterministic on
# the WSL swiftshader path. This boots the pinned AVD once, waits until it is
# genuinely ready, and saves a named snapshot. Afterwards `make emulator`
# restores from it in seconds with a known-clean state (emu_boot … <snapshot>).
# Re-run whenever the system image or host changes (the snapshot is invalidated).
#
# Env knobs:
#   AVD          AVD name        (default pixel8_api34)
#   EMU_SERIAL   adb serial      (default emulator-5554)
#   EMU_PORT     console port    (default 5554)
#   SNAPSHOT     snapshot name   (default golden)
#   READY_WAIT   boot timeout s  (default 300)
#
# Usage: bash toolchain/emulator_snapshot.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
# shellcheck source=toolchain/device_loop.sh
. "$ROOT/toolchain/device_loop.sh"

AVD="${AVD:-pixel8_api34}"
EMU_SERIAL="${EMU_SERIAL:-emulator-5554}"
EMU_PORT="${EMU_PORT:-5554}"
SNAPSHOT="${SNAPSHOT:-golden}"
READY_WAIT="${READY_WAIT:-300}"

fail() { echo "EMULATOR-SNAPSHOT: FAIL — $*" >&2; exit 1; }

kvm_available || echo "==> WARNING: /dev/kvm not usable — cold boot will be slow."

echo "==> [1/4] cold-booting $AVD as $EMU_SERIAL (port $EMU_PORT, writable)"
# Writable boot: the emulator refuses to SAVE a snapshot in -read-only mode.
EMU_READONLY=0 emu_boot "$AVD" "$EMU_SERIAL" "$EMU_PORT" ""

echo "==> [2/4] waiting up to ${READY_WAIT}s for full readiness"
emu_wait_ready "$EMU_SERIAL" "$READY_WAIT" || {
    emu_stop "$EMU_SERIAL"
    fail "AVD did not become ready within ${READY_WAIT}s"
}
echo "    ready (boot_completed + bootanim stopped + pm responding)"

echo "==> [3/4] saving snapshot '$SNAPSHOT'"
adbq -s "$EMU_SERIAL" emu avd snapshot save "$SNAPSHOT" \
    || fail "snapshot save failed (is the AVD writable / not -read-only?)"

echo "==> [4/4] stopping emulator"
emu_stop "$EMU_SERIAL"

echo "EMULATOR-SNAPSHOT: OK"
echo "  avd=$AVD  snapshot=$SNAPSHOT"
echo "  next: make emulator   (restores from '$SNAPSHOT' in seconds)"
