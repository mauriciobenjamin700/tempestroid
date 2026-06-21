#!/usr/bin/env bash
# dual-verify — orchestrate the enforced dual-renderer verification (Qt + device).
# Usage: bash .claude/skills/dual-verify/verify.sh [APP]
#   APP   app file to exercise (default: examples/counter/app.py)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
SKILLS="$ROOT/.claude/skills"
SDK="${ANDROID_SDK_ROOT:-/usr/lib/android-sdk}"
APP="${1:-examples/counter/app.py}"

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YEL="\033[33m"; CYAN="\033[36m"; RESET="\033[0m"
section() { printf "\n${BOLD}==> %s${RESET}\n" "$1"; }
cmd()     { printf "    ${CYAN}%s${RESET}\n" "$1"; }

FAIL=0

# --- decide the path ---------------------------------------------------------
section "detecting connected device"
if [[ -x "$SDK/platform-tools/adb" ]]; then ADB="$SDK/platform-tools/adb"; else ADB="adb"; fi
DEVICE=0
if command -v "$ADB" >/dev/null 2>&1 || [[ -x "$ADB" ]]; then
  # Time-bound the probe: a wedged adb server (device dropped off USB-WSL) would
  # otherwise hang here — the failure mode Trilho F5 hardens against.
  n_ok=$(timeout 20 "$ADB" devices 2>/dev/null | awk 'NR>1 && $2=="device"{c++} END{print c+0}')
  if [[ "$n_ok" -ge 1 ]]; then
    DEVICE=1
    printf "${GREEN}device connected${RESET} — dual path: Qt + Compose required\n"
  else
    printf "${YEL}no device${RESET} — Qt-only path (device half cannot be exercised)\n"
  fi
else
  printf "${YEL}adb unavailable${RESET} — Qt-only path\n"
fi

# --- leg 1: Qt (always) ------------------------------------------------------
section "Qt leg — quality gates (framework-guard)"
if bash "$SKILLS/framework-guard/check.sh"; then :; else FAIL=1; fi

section "Qt leg — run the simulator yourself and eyeball it"
echo "  The Qt sim is interactive; run one of these, exercise the changed flow, screenshot it:"
cmd "make run APP=$APP        # one-shot"
cmd "make dev APP=$APP        # hot restart loop (r/R/s/q)"

# --- leg 2: device (only if connected) ---------------------------------------
if [[ $DEVICE -eq 1 ]]; then
  section "device leg — toolchain preflight (android-doctor)"
  if bash "$SKILLS/android-doctor/check.sh"; then :; else
    FAIL=1
    printf "${RED}android-doctor failed${RESET} — fix the toolchain before the device build\n"
  fi

  section "device leg — build/install + exercise on the real device"
  echo "  Pick ONE, then run the SAME flow you ran in Qt and screenshot it:"
  echo "  (parallel agents: export ANDROID_ADB_SERVER_PORT=<5038..5500> + ANDROID_SERIAL"
  echo "   first for a PRIVATE adb server — never 'adb kill-server'/'pkill -x adb', it"
  echo "   drops every agent's server. 'tempest uitest --isolate-adb' auto-allocates one.)"
  cmd "make apk-install            # rebuild + adb install the APK"
  cmd "tempest serve $APP   # live code-push over adb reverse (no rebuild)"
  cmd "make logcat                 # tail device logs for runtime errors"
  echo
  echo "  For a FULL widget-surface sweep (all examples, screenshots + traceback scan),"
  echo "  use the hardened F5 harness — it is USB-drop-safe and RESUMES on re-run:"
  cmd "bash toolchain/validate_gallery.sh    # checkpointed; FRESH=1 to restart"
  echo "  If it prints an 'ABORT … usb-drop' line, the device fell off USB mid-run:"
  echo "  the device half is NOT verified — re-attach (usbipd attach --wsl --busid <id>)"
  echo "  and re-run to resume. Do NOT report device parity off a partial sweep."
  cat <<EOF

  On-device checklist (known gotchas):
    [ ] Buttons honor the Style background (no stray Material purple).
    [ ] Dense/operator-key layouts keep their spacing/arrangement.
    [ ] The changed flow behaves identically to the Qt sim.
    [ ] Screenshot captured (the rule REQUIRES it for the device leg).
    [ ] If the gallery harness ran: no 'ABORT … usb-drop' in /tmp/gallery_results.txt.
EOF
else
  section "device leg — SKIPPED (no device)"
  cat <<EOF
  ${YEL}MANDATORY disclaimer when you report this change:${RESET}
    "Device half NOT exercised — no Android device connected; verified on Qt only."
  Do NOT claim Compose/device parity without running on hardware.
EOF
fi

# --- summary -----------------------------------------------------------------
section "summary"
if [[ $FAIL -ne 0 ]]; then
  printf "${RED}dual-verify: a gate FAILED${RESET} — change is NOT done.\n"
  exit 1
fi
if [[ $DEVICE -eq 1 ]]; then
  printf "${GREEN}dual-verify: gates green${RESET} — now run BOTH legs above (Qt + device) and screenshot each before reporting done.\n"
else
  printf "${GREEN}dual-verify: gates green${RESET} — run the Qt leg + screenshot; state the device half was NOT exercised.\n"
fi
exit 0
