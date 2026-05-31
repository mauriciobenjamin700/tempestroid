#!/usr/bin/env bash
# parity-phase — scaffold + gate a Trilho E (Flutter/RN parity) phase or sub-task.
# Usage: bash .claude/skills/parity-phase/plan.sh <phase-id>   (e.g. E0, E2a)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
SKILLS="$ROOT/.claude/skills"
PLAN="docs/plan-parity.md"

PHASE_IN="${1:-}"
if [[ -z "$PHASE_IN" ]]; then
  echo "usage: plan.sh <phase-id>   (e.g. E0, E2a)"
  exit 2
fi
# A sub-task (E2a) maps to its parent phase section (## E2 — …).
PARENT=$(echo "$PHASE_IN" | grep -oE '^E[0-9]+')
if [[ -z "$PARENT" ]]; then
  echo "phase id must look like E0 / E2a"
  exit 2
fi

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YEL="\033[33m"; CYAN="\033[36m"; RESET="\033[0m"
section() { printf "\n${BOLD}==> %s${RESET}\n" "$1"; }

if [[ ! -f "$PLAN" ]]; then
  printf "${RED}FAIL${RESET}  %s not found\n" "$PLAN"
  exit 1
fi

# --- 1) print the phase spec section -----------------------------------------
section "spec for $PHASE_IN (from $PLAN — parent phase $PARENT)"
# Extract from the "## E<n> —" header up to (but not including) the next "## " header.
spec=$(awk -v p="$PARENT" '
  $0 ~ "^## " p " " {grab=1}
  grab && $0 ~ "^## " && $0 !~ "^## " p " " && NR>1 && seen {exit}
  grab {print; seen=1}
' "$PLAN")
if [[ -z "$spec" ]]; then
  printf "${YEL}WARN${RESET}  no '## %s —' section in %s\n" "$PARENT" "$PLAN"
else
  echo "$spec"
fi

# --- 2) resolve the Arquivos anchors -----------------------------------------
section "Arquivos anchors — exists (edit) vs new (create)"
# Pull file-ish tokens from the spec's "Arquivos" block: backticked paths with a
# slash or a .py/.kt extension.
paths=$(echo "$spec" | grep -oE '`[a-zA-Z0-9_./-]+\.(py|kt)`' | tr -d '`' | sort -u)
if [[ -z "$paths" ]]; then
  printf "${YEL}WARN${RESET}  no file anchors parsed — read the Arquivos block above\n"
else
  while IFS= read -r p; do
    [[ -z "$p" ]] && continue
    # Resolve android-host paths that the spec abbreviates with ".../".
    if [[ -e "$p" ]]; then
      printf "  ${GREEN}edit  ${RESET} %s\n" "$p"
    elif compgen -G "$p" >/dev/null 2>&1; then
      printf "  ${GREEN}edit  ${RESET} %s\n" "$p"
    else
      base=$(basename "$p")
      hit=$(find tempestroid android-host tests -name "$base" 2>/dev/null | head -1)
      if [[ -n "$hit" ]]; then
        printf "  ${GREEN}edit  ${RESET} %s  ${CYAN}(found: %s)${RESET}\n" "$p" "$hit"
      else
        printf "  ${YEL}new   ${RESET} %s\n" "$p"
      fi
    fi
  done <<< "$paths"
fi

# --- 3) three-layer presence heuristic ---------------------------------------
section "three-layer invariant (IR + Qt + Compose + conformance)"
echo "  Every E phase must land all matched layers it touches. Quick presence scan:"
layer() {
  local label="$1" glob="$2"
  if compgen -G "$glob" >/dev/null 2>&1; then
    printf "  ${GREEN}present${RESET} %-22s (%s)\n" "$label" "$glob"
  else
    printf "  ${YEL}MISSING${RESET} %-22s (%s)\n" "$label" "$glob"
  fi
}
layer "Qt translator"      "tempestroid/renderers/qt/style_translator.py"
layer "Compose translator" "tempestroid/renderers/compose/style_translator.py"
layer "conformance suite"  "tests/conformance/test_conformance.py"
cat <<EOF

  ${BOLD}Checklist (the script can't prove these — you must):${RESET}
    [ ] New widget re-exported in widgets/__init__.py AND tempestroid/__init__.py (+ __all__).
    [ ] New event: frozen in events.py, in event_schemas, parse_event, event_type_for, introspect().
    [ ] New Style field: BOTH style_translator.py files + a tests/conformance/ golden.
    [ ] Qt leg AND Compose leg both implemented (not one renderer only).
    [ ] Native capability uses the B6 pattern (no C change unless a new stream token).
EOF

# --- 4) chain the gates ------------------------------------------------------
FAIL=0
section "gate — framework-guard (Python: ruff + pyright + pytest + conventions + docs)"
if bash "$SKILLS/framework-guard/check.sh"; then :; else FAIL=1; fi

section "dual-renderer verification"
printf "  Run the enforced dual check (Qt + device) before closing:\n"
printf "    ${CYAN}bash %s/dual-verify/verify.sh <APP>${RESET}\n" "$SKILLS"

section "summary"
if [[ $FAIL -eq 0 ]]; then
  printf "${GREEN}parity-phase: Python gate PASS${RESET} — verify the checklist + run dual-verify, then close $PHASE_IN.\n"
else
  printf "${RED}parity-phase: Python gate FAIL${RESET} — do NOT close $PHASE_IN until green.\n"
fi
exit $FAIL
