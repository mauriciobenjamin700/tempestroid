#!/usr/bin/env bash
# phase-closer — validate a roadmap phase's "done when" before marking it ✅.
# Usage: bash .claude/skills/phase-closer/close.sh <phase-id>   (e.g. A4, B2, C)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
SKILLS="$ROOT/.claude/skills"

PHASE="${1:-}"
if [[ -z "$PHASE" ]]; then
  echo "usage: close.sh <phase-id>   (e.g. A4, B2, C)"
  exit 2
fi

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YEL="\033[33m"; RESET="\033[0m"
section() { printf "\n${BOLD}==> %s${RESET}\n" "$1"; }

section "done-when for phase $PHASE (from CLAUDE.md)"
row=$(grep -E "^\|\s*${PHASE}\b" CLAUDE.md || true)
if [[ -n "$row" ]]; then
  echo "$row"
else
  printf "${YEL}WARN${RESET}  no phase row matching '%s' in CLAUDE.md table\n" "$PHASE"
fi

section "plan.md description"
desc=$(grep -nE "\*\*${PHASE} —|\*\*${PHASE}—" docs/plan.md || true)
if [[ -n "$desc" ]]; then
  echo "$desc"
else
  printf "${YEL}WARN${RESET}  no '**%s —**' entry in docs/plan.md\n" "$PHASE"
fi

FAIL=0

section "gate 1/2 — framework-guard"
if bash "$SKILLS/framework-guard/check.sh"; then :; else FAIL=1; fi

section "gate 2/2 — docs-sync-check"
if uv run python "$SKILLS/docs-sync-check/check.py"; then :; else FAIL=1; fi

section "manual done-when checklist"
cat <<EOF
  [ ] The done-when criterion above is genuinely met (not partially).
  [ ] A specific test backs it — name it: ____________________
  [ ] Status flipped in BOTH CLAUDE.md and README.md phase tables.
  [ ] docs/plan.md notes updated if needed.
EOF

section "summary"
if [[ $FAIL -eq 0 ]]; then
  printf "${GREEN}phase-closer: automated gates PASS${RESET} — verify the manual checklist, then close $PHASE.\n"
else
  printf "${RED}phase-closer: automated gates FAIL${RESET} — do NOT close $PHASE until green.\n"
fi
exit $FAIL
