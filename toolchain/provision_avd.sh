#!/usr/bin/env bash
# provision_avd.sh — create the pinned headless x86_64 AVD, idempotently (F8).
#
# The whole team (and CI) needs the SAME emulator, recreatable from zero — no
# "works on my machine". This installs the exact system image and creates the
# AVD pinning API + ABI + profile. Running it again when the AVD already exists
# is a no-op (unless FORCE=1 recreates it). It does NOT boot the AVD — that is
# `make emulator` (snapshot-aware) via toolchain/device_loop.sh.
#
# Env knobs:
#   AVD         AVD name                    (default pixel8_api34)
#   API         Android API level           (default 34)
#   ABI         system-image ABI            (default x86_64)
#   TAG         system-image tag            (default google_apis)
#   DEVICE      hardware profile id         (default pixel_8)
#   FORCE=1     delete + recreate if present
#
# Usage: bash toolchain/provision_avd.sh
set -euo pipefail

AVD="${AVD:-pixel8_api34}"
API="${API:-34}"
ABI="${ABI:-x86_64}"
TAG="${TAG:-google_apis}"
DEVICE="${DEVICE:-pixel_8}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
export ANDROID_SDK_ROOT

IMAGE="system-images;android-${API};${TAG};${ABI}"
SDKMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager"

fail() { echo "PROVISION-AVD: FAIL — $*" >&2; exit 1; }

[ -x "$SDKMANAGER" ] || fail "sdkmanager not at $SDKMANAGER (install cmdline-tools)"
[ -x "$AVDMANAGER" ] || fail "avdmanager not at $AVDMANAGER (install cmdline-tools)"

if [ ! -r /dev/kvm ] || [ ! -w /dev/kvm ]; then
    echo "==> WARNING: /dev/kvm not usable — a headless AVD will be very slow."
    echo "    On a host without KVM (CI without nested virt), use a cloud device"
    echo "    farm instead (see docs/guia/dispositivo-wsl.md)."
fi

echo "==> [1/3] ensure system image: $IMAGE"
yes 2>/dev/null | "$SDKMANAGER" --install "$IMAGE" >/dev/null || fail "sdkmanager install failed"

echo "==> [2/3] AVD '$AVD' (device=$DEVICE, image=$IMAGE)"
if "$AVDMANAGER" list avd 2>/dev/null | grep -q "Name: ${AVD}\b"; then
    if [ "${FORCE:-0}" = "1" ]; then
        echo "    exists — FORCE=1, deleting + recreating"
        "$AVDMANAGER" delete avd --name "$AVD" >/dev/null 2>&1 || true
    else
        echo "    already provisioned — no-op (FORCE=1 to recreate)"
        echo "PROVISION-AVD: OK (existing)"
        exit 0
    fi
fi

echo "==> [3/3] creating AVD '$AVD'"
echo "no" | "$AVDMANAGER" create avd \
    --name "$AVD" \
    --package "$IMAGE" \
    --device "$DEVICE" \
    --force >/dev/null || fail "avdmanager create failed"

echo "PROVISION-AVD: OK"
echo "  avd=$AVD  image=$IMAGE  device=$DEVICE"
echo "  next: make emulator-snapshot  (boot once + save the 'golden' snapshot)"
echo "        make emulator           (fast boot from the snapshot)"
