# `.workflow-runtime/` — the gitignored live-state layer (control-plane spec §1.2)

**Status:** the `.gitignore` rule is live; the directory + its contents are created **lazily by tooling**
(dispatch, doctor/recover, loops) — most of which is still DESIGN (spec §10). This doc defines the intended
layout so those tools populate a consistent shape. Do not hand-fabricate runtime state to look "live."

## Why it is out of git
the framework dir (tracked) = durable framework assets — reviewable, shared via `.git`, cannot drift.
`.workflow-runtime/` (gitignored) = operational exhaust — dispatch queue, journals, checkpoints, heartbeats,
restore snapshots, loop leases. Committing exhaust creates repo churn, merge noise, secret-leak risk, and
misleading history. So it is deliberately **local-only**.

## Sharing across worktrees (canonical main-root, self-resolved)
Worktrees are separate directories, so a *shared* runtime store (esp. the cross-stream **dispatch queue**)
cannot live in a per-worktree `.workflow-runtime/`. **The main root's `.workflow-runtime/` is canonical.**
`dispatch.py` and `doctor.py` **self-resolve it** via `git rev-parse --git-common-dir` (the shared `.git`
→ its parent is the main root), so every worktree reads/writes the *same* queue with **no symlink required**.
An optional `.workflow-runtime → <main-root>/.workflow-runtime` symlink (reports-style) is only for other
tools that want the dir visible locally. Per-worktree-only state (a worktree's journal) can still live under
a stream-keyed subdir. **Live as of the dispatch build (`scripts/dispatch.py`).**

## Intended layout
```
.workflow-runtime/
  dispatch/            # append-only addressed envelopes (spec §3.3, §7.3); consumers set lease/ack
  journals/<stream>/   # per-stream Stop-hook breadcrumbs (or keep STATE.journal.md per worktree)
  checkpoints/         # loop + long-task checkpoints
  leases/              # loop lease + heartbeat files (spec §3.5)
  snapshots/           # DR recovery-report snapshots (spec §3.4, §7.5)
  overrides/           # logged human overrides: stop-loop / force-route / ignore-stale (spec §11)
```

Note: today's per-worktree `STATE.journal.md` and `.claude/transcript-backups/` already play the
journal/backup role; they migrate under `.workflow-runtime/` (or stay, symlinked) when the layer is wired.
