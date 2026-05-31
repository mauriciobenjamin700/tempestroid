#!/usr/bin/env bash
# framework-guard — run tempestroid's quality gates + convention heuristics.
# Usage: bash .claude/skills/framework-guard/check.sh [--quick]
#   --quick   skip pytest (lint + types + conventions only)
set -uo pipefail

# Resolve repo root (two levels up from this script: .claude/skills/<name>/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

QUICK=0
[[ "${1:-}" == "--quick" ]] && QUICK=1

FAIL=0
section() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
ok()      { printf "\033[32mPASS\033[0m  %s\n" "$1"; }
bad()     { printf "\033[31mFAIL\033[0m  %s\n" "$1"; FAIL=1; }

section "ruff (lint / imports / quotes / docstrings)"
if uv run ruff check .; then ok "ruff"; else bad "ruff"; fi

section "pyright (strict type check)"
if uv run pyright; then ok "pyright"; else bad "pyright"; fi

if [[ $QUICK -eq 0 ]]; then
  section "pytest (full suite)"
  if uv run pytest; then ok "pytest"; else bad "pytest"; fi
else
  printf "\n(skipping pytest: --quick)\n"
fi

section "convention heuristics (beyond ruff)"

# 1) Single-quoted string literals in src/. ruff's flake8-quotes (Q) is the
#    source of truth and already ran above; it ALLOWS single quotes when the
#    string contains a double quote (avoid-escape). So we only net single-quoted
#    strings that do NOT contain a `"` and aren't in a comment — the cases ruff
#    would also reject — as a redundant guard.
sq=$(grep -rnP "(?<![\\w'])'(?:[^'\"\\\\\n]|\\\\.)*'" src/tempestroid --include="*.py" \
      | grep -vP "^\s*[^:]+:[0-9]+:\s*#" || true)
if [[ -n "$sq" ]]; then
  bad "single-quoted strings found (use double quotes):"
  echo "$sq" | sed 's/^/      /'
else
  ok "no single-quoted strings in src/ (ruff Q is authoritative)"
fi

# 2) __init__.py missing __all__.
missing_all=""
while IFS= read -r f; do
  grep -q "__all__" "$f" || missing_all+="$f"$'\n'
done < <(find src/tempestroid -name "__init__.py")
if [[ -n "$missing_all" ]]; then
  bad "__init__.py without __all__:"
  printf '%s' "$missing_all" | sed 's/^/      /'
else
  ok "every package __init__.py declares __all__"
fi

# 3) Empty placeholder packages: dir whose only .py file is __init__.py AND that
#    holds no subpackage with modules (a pure namespace like renderers/ is fine).
empty_pkgs=""
while IFS= read -r d; do
  pys=$(find "$d" -maxdepth 1 -name "*.py" | wc -l)
  subpys=$(find "$d" -mindepth 2 -name "*.py" -not -name "__init__.py" \
            -not -path "*__pycache__*" | wc -l)
  [[ "$pys" -le 1 && "$subpys" -eq 0 ]] && empty_pkgs+="$d"$'\n'
done < <(find src/tempestroid -type d -not -path "*__pycache__*")
# Drop the package root itself only if it legitimately holds modules; report leaves.
empty_pkgs=$(printf '%s' "$empty_pkgs" | grep -v "^$" || true)
if [[ -n "$empty_pkgs" ]]; then
  # Only warn — a package mid-build may legitimately have just __init__.py briefly.
  printf "\033[33mWARN\033[0m  packages with only __init__.py (no placeholders allowed if permanent):\n"
  printf '%s\n' "$empty_pkgs" | sed 's/^/      /'
else
  ok "no empty placeholder packages"
fi

section "summary"
if [[ $FAIL -eq 0 ]]; then
  printf "\033[32mframework-guard: PASS\033[0m\n"
else
  printf "\033[31mframework-guard: FAIL\033[0m\n"
fi
exit $FAIL
