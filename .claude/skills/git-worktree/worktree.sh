#!/usr/bin/env bash
# git-worktree — isolate parallel work in its own git worktree so concurrent
# agents never share a working tree. A shared tree lets a parallel agent switch
# HEAD or leave uncommitted files mid-run, so commits land on the wrong branch
# and unrelated changes leak into a PR. One worktree per agent/task prevents it.
# Usage:
#   bash .claude/skills/git-worktree/worktree.sh new <branch> [base]
#   bash .claude/skills/git-worktree/worktree.sh list
#   bash .claude/skills/git-worktree/worktree.sh rm <branch> [--force]
#   bash .claude/skills/git-worktree/worktree.sh prune
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
REPO="$(basename "$ROOT")"
WT_HOME="$(cd "$ROOT/.." && pwd)/${REPO}-worktrees"

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YEL="\033[33m"; RESET="\033[0m"
info() { printf "${GREEN}%s${RESET}\n" "$1"; }
warn() { printf "${YEL}%s${RESET}\n" "$1"; }
die()  { printf "${RED}%s${RESET}\n" "$1" >&2; exit 1; }

# Sanitize a branch name into a directory-safe slug (slashes → dashes).
slug() { printf "%s" "$1" | tr '/' '-' | tr -cs 'A-Za-z0-9._-' '-'; }

cmd="${1:-}"; shift || true

case "$cmd" in
  new)
    branch="${1:-}"; base="${2:-origin/main}"
    [[ -z "$branch" ]] && die "usage: worktree.sh new <branch> [base]   (e.g. fix/foo)"
    dir="$WT_HOME/$(slug "$branch")"
    [[ -e "$dir" ]] && die "worktree dir already exists: $dir"
    info "fetching origin (so $base is current)…"
    git fetch origin --quiet || warn "git fetch failed — using local $base"
    mkdir -p "$WT_HOME"
    # Re-use the branch if it already exists; otherwise create it off base.
    if git show-ref --verify --quiet "refs/heads/$branch"; then
      git worktree add "$dir" "$branch" || die "worktree add failed"
    else
      git worktree add -b "$branch" "$dir" "$base" || die "worktree add failed"
    fi
    printf "${BOLD}worktree ready${RESET}: %s   (branch %s off %s)\n" "$dir" "$branch" "$base"
    cat <<EOF

  Next:
    cd $dir
    uv sync            # install deps in the isolated tree (only if you run code)
    # …work, commit ONLY your own files, open the PR from here…
    bash .claude/skills/git-worktree/worktree.sh rm $branch   # when done + merged
EOF
    ;;
  list)
    git worktree list
    ;;
  rm|remove)
    branch="${1:-}"; force="${2:-}"
    [[ -z "$branch" ]] && die "usage: worktree.sh rm <branch> [--force]"
    dir="$WT_HOME/$(slug "$branch")"
    [[ -d "$dir" ]] || die "no worktree dir at $dir (run 'list' to see them)"
    if [[ "$force" == "--force" ]]; then
      git worktree remove --force "$dir" && info "removed $dir (forced)"
    else
      if git worktree remove "$dir"; then
        info "removed $dir"
      else
        die "remove failed — uncommitted changes? commit/push first, or re-run with --force"
      fi
    fi
    ;;
  prune)
    git worktree prune -v
    info "pruned stale worktree metadata"
    ;;
  *)
    cat <<EOF
git-worktree — one isolated working tree per parallel task.

  new <branch> [base]    create ../${REPO}-worktrees/<branch> off base (default origin/main)
  list                   show all worktrees
  rm <branch> [--force]  remove a worktree (refuses if dirty unless --force)
  prune                  drop stale worktree metadata

Why: a shared working tree lets a parallel agent switch HEAD or leave
uncommitted files mid-run, so commits land on the wrong branch and unrelated
changes leak into a PR. One worktree per agent/task prevents that.
EOF
    [[ -n "$cmd" ]] && die "unknown command: $cmd"
    ;;
esac
