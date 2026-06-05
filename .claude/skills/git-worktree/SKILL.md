---
name: git-worktree
description: Create and manage an isolated git worktree per parallel task, so concurrent agents never share one working tree (a shared tree lets one switch HEAD or leave uncommitted files mid-run — commits land on the wrong branch, unrelated changes leak into the PR). Use BEFORE starting work that may run alongside another agent/task in this repo, when asked to "use a worktree" / "isolate this work" / "trabalhar em paralelo", or after a shared-tree mishap (branch hijacked, lost edits, mixed diff).
---

# git-worktree

A `git worktree` is a second working directory backed by the same `.git`, on its
own branch. Two agents in two worktrees can build, commit and open PRs at the
same time without ever stepping on each other.

This repo has already been bitten by the shared-tree hazard: a concurrent task
switched the checkout's branch and reset tracked files mid-run, so edits had to
be recovered from a pushed branch. The rule (also in `CLAUDE.md` → Git): **one
worktree per agent/task whenever work may run in parallel.**

## When to use

- **Before** starting a task that could overlap another agent's work in this
  repo (the common case for any background/parallel run).
- When the user says "use a worktree", "isolate this", "trabalhar em paralelo",
  "um worktree por agente".
- **After** a shared-tree mishap — branch switched under you, uncommitted edits
  vanished, or a diff mixed two unrelated changes. Move to a worktree and
  recover from the pushed branch.

## How to run

```bash
# create an isolated tree + branch off the current origin/main
bash .claude/skills/git-worktree/worktree.sh new fix/my-task
# off a different base
bash .claude/skills/git-worktree/worktree.sh new feat/x origin/dev

bash .claude/skills/git-worktree/worktree.sh list          # show all worktrees
bash .claude/skills/git-worktree/worktree.sh rm fix/my-task    # remove when merged
bash .claude/skills/git-worktree/worktree.sh rm fix/my-task --force  # discard a dirty tree
bash .claude/skills/git-worktree/worktree.sh prune         # drop stale metadata
```

`new`:

1. `git fetch origin` so the base ref is current.
2. Creates `../<repo>-worktrees/<branch-slug>` (a sibling dir — outside the repo,
   so the framework gates never scan it; slashes in the branch become dashes).
3. `git worktree add -b <branch> <dir> <base>` (re-uses the branch if it already
   exists), then prints the `cd` + `uv sync` next steps.

## Workflow inside a worktree

1. `cd ../<repo>-worktrees/<branch-slug>`.
2. `uv sync` only if you'll run code there (each tree has its own checkout; the
   `.venv` can be created per-tree).
3. Work, run the gates (`framework-guard`, `dual-verify`), **commit only your own
   files**, push, and open the PR **from the worktree** — build/implementation
   agents stop at "PR opened" and never merge (see `CLAUDE.md` → Workflow).
4. When the PR is merged (or abandoned), `rm <branch>` to delete the tree;
   `prune` clears any leftover metadata.

## Notes

- Never `git checkout`/`switch` branches in a tree another agent is using — that
  is the exact hazard worktrees exist to avoid. Make a new worktree instead.
- The worktree dir is intentionally a sibling of the repo, not nested inside it,
  so `ruff`/`pyright`/`pytest` and the asset bundler don't pick it up.
- A worktree shares the object store, so it is cheap; `rm` only deletes the
  checkout dir + its branch's worktree link, not the branch or its commits.
