#!/usr/bin/env bash
# android-doctor — validate the Trilho B (Android) build/run toolchain on this host.
# Usage: bash .claude/skills/android-doctor/check.sh [--quick]
#   --quick   skip the device/adb checks (host-only: SDK/NDK/JDK/Gradle/staging)
set -uo pipefail

# Resolve repo root (three levels up: .claude/skills/<name>/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

QUICK=0
[[ "${1:-}" == "--quick" ]] && QUICK=1

# Resolve the SDK: the env's ANDROID_SDK_ROOT/ANDROID_HOME are often stale on this
# host (point at a non-existent ~/Android/Sdk); the real SDK lives at
# /usr/lib/android-sdk (see CLAUDE.md). Prefer whichever candidate actually has
# platform-tools/adb, env value first.
SDK=""
for cand in "${ANDROID_SDK_ROOT:-}" "/usr/lib/android-sdk" "${ANDROID_HOME:-}"; do
  [[ -n "$cand" && -x "$cand/platform-tools/adb" ]] && { SDK="$cand"; break; }
done
# Fall back to the env value (or the documented default) for the failure message.
SDK="${SDK:-${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}}"
ANDROID="android-host"
WANT_GRADLE="8.11.1"

FAIL=0
section() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
ok()      { printf "\033[32mPASS\033[0m  %s\n" "$1"; }
bad()     { printf "\033[31mFAIL\033[0m  %s\n" "$1"; FAIL=1; }
warn()    { printf "\033[33mWARN\033[0m  %s\n" "$1"; }

section "Android SDK root"
if [[ -x "$SDK/platform-tools/adb" ]]; then
  ok "SDK at $SDK (adb found)"
  if [[ -n "${ANDROID_SDK_ROOT:-}" && "${ANDROID_SDK_ROOT}" != "$SDK" ]]; then
    warn "env ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT is stale/invalid — using $SDK instead; export ANDROID_SDK_ROOT=$SDK"
  fi
else
  bad "no adb under '$SDK/platform-tools' — export ANDROID_SDK_ROOT=/usr/lib/android-sdk"
fi

section "NDK"
if [[ -d "$SDK/ndk" ]] && find "$SDK/ndk" -maxdepth 1 -mindepth 1 -type d | grep -q .; then
  ndk_ver=$(find "$SDK/ndk" -maxdepth 1 -mindepth 1 -type d -printf '%f ' 2>/dev/null)
  ok "NDK present: $ndk_ver"
else
  bad "no NDK under '$SDK/ndk' — native libpython/libtempest_host build needs it"
fi

section "JDK"
if command -v java >/dev/null 2>&1; then
  jver=$(java -version 2>&1 | head -1)
  ok "java found: $jver"
else
  bad "java not on PATH — AGP 8.7 needs JDK 17+"
fi

section "Gradle wrapper (must be $WANT_GRADLE, not the global Gradle)"
wrapper_props="$ANDROID/gradle/wrapper/gradle-wrapper.properties"
if [[ -x "$ANDROID/gradlew" && -f "$wrapper_props" ]]; then
  if grep -q "gradle-${WANT_GRADLE}-" "$wrapper_props"; then
    ok "gradlew pinned to $WANT_GRADLE"
  else
    got=$(grep -oE "gradle-[0-9.]+-(bin|all)" "$wrapper_props" | head -1)
    bad "wrapper is '$got', expected gradle-$WANT_GRADLE (AGP 8.7 breaks on Gradle 9.x)"
  fi
else
  bad "no $ANDROID/gradlew or wrapper props — run the device build via the bundled wrapper only"
fi

section "Staged runtime (CPython 3.14 + wheels)"
if [[ -f "toolchain/dist/python/arm64-v8a/libpython3.14.so" ]]; then
  ok "libpython3.14.so staged (arm64-v8a)"
else
  warn "toolchain/dist/python/arm64-v8a/libpython3.14.so missing — run 'make toolchain'"
fi
if [[ -d "toolchain/dist/site-packages/pydantic" ]]; then
  ok "site-packages staged (pydantic present)"
else
  warn "toolchain/dist/site-packages/pydantic missing — run 'make toolchain'"
fi

if [[ $QUICK -eq 0 ]]; then
  section "Connected device (adb)"
  if [[ -x "$SDK/platform-tools/adb" ]]; then
    ADB="$SDK/platform-tools/adb"
  else
    ADB="adb"
  fi
  # Every adb call here is time-bounded: a wedged adb server (e.g. after the
  # device drops off USB-WSL) would otherwise hang `adb devices` forever — the
  # exact failure that motivated Trilho F5.
  adbq() { timeout 20 "$ADB" "$@"; }
  if command -v "$ADB" >/dev/null 2>&1 || [[ -x "$ADB" ]]; then
    devices=$(adbq devices | awk 'NR>1 && $1 != "" {print}')
    n_ok=$(echo "$devices" | awk '$2=="device"{c++} END{print c+0}')
    n_bad=$(echo "$devices" | awk '$2=="unauthorized"||$2=="offline"{c++} END{print c+0}')
    if [[ "$n_ok" -eq 1 ]]; then
      serial=$(echo "$devices" | awk '$2=="device"{print $1; exit}')
      abi=$(adbq -s "$serial" shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')
      ok "1 device in 'device' state: $serial (abi=$abi)"
      [[ "$abi" == "arm64-v8a" ]] || warn "abi is '$abi', not arm64-v8a — needs the matching staged wheel/runtime"
      # Stability probe: two spaced get-state reads. A device that flaps on
      # USB-WSL passes the first `adb devices` but drops mid-build — catch it now.
      s1=$(adbq get-state 2>/dev/null | tr -d '\r'); sleep 2
      s2=$(adbq get-state 2>/dev/null | tr -d '\r')
      if [[ "$s1" == "device" && "$s2" == "device" ]]; then
        ok "device stable (two spaced get-state reads)"
      else
        warn "device state flapped ('$s1' → '$s2') — USB-WSL link is unstable; re-attach (usbipd attach --wsl --busid <id>) before a long device-verify run"
      fi
    elif [[ "$n_ok" -gt 1 ]]; then
      warn "$n_ok devices connected — pass -s <serial> to adb / Gradle to disambiguate"
    elif [[ "$n_bad" -gt 0 ]]; then
      bad "device(s) in unauthorized/offline — accept the USB-debugging prompt; on MIUI enable 'Install via USB'"
    else
      warn "no device connected — device half cannot be exercised on this host (Trilho A / Qt only)"
    fi
  else
    bad "adb unavailable — fix the SDK root above"
  fi
else
  printf "\n(skipping device checks: --quick)\n"
fi

section "summary"
if [[ $FAIL -eq 0 ]]; then
  printf "\033[32mandroid-doctor: PASS\033[0m  (warnings above are non-fatal)\n"
else
  printf "\033[31mandroid-doctor: FAIL\033[0m  — fix the toolchain before building/installing the APK\n"
fi
exit $FAIL
