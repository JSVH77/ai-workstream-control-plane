---
name: vendor-memory-is-base-project-scoped
description: "EMPIRICAL: the vendor MEMORY.md bucket is keyed on the BASE PROJECT (main worktree path), not the per-worktree cwd. ALL worktrees read AND write the SAME bucket. The look-alike per-worktree buckets exist on disk but are never loaded — inert. Only STATE.md is per-worktree."
metadata:
  node_type: memory
  type: feedback
---

## The finding (from a real restart + a write probe, not from reasoning)

A stream was restarted for real inside a **non-main** worktree. Its SessionStart injected `MEMORY.md` from
the **MAIN** bucket — `~/.claude/projects/<main-worktree-abs-path-slug>/memory/` — verified by path, byte
size, and content markers (it carried the main bucket's markers and **zero** markers unique to that
worktree's own look-alike bucket, which also existed on disk and was **not** the one that loaded).

**Read and write are both MAIN (symmetric)** — confirmed by a write probe: a uniquely-marked test file
written from the non-main worktree's session landed in the **MAIN** bucket.

**Conclusion: the vendor keys the memory bucket on the BASE PROJECT, not the worktree cwd.** There is
effectively **ONE shared bucket per repo**, read+write, for every worktree session.

## Two different keying mechanisms (the crux)

| Layer | Keyed on | Scope |
|---|---|---|
| `STATE.md` (the SessionStart hook) | `$CLAUDE_PROJECT_DIR` = the worktree | **per-worktree** ✓ |
| vendor auto-memory (`MEMORY.md` + notes) | the base project (main worktree path) | **shared across all worktrees** |

So a stream's *identity* rides on its STATE; its *knowledge* is a common pool.

## What this invalidates

- **"Memory is per-session and drifts"** — wrong. The *files* differ per path, but only the base-project
  bucket is ever **loaded**. It is base-project-**shared**, not per-worktree-drifting.
- **Per-worktree buckets are DEAD for loading.** Do not migrate memories into one to "arm" a stream for
  restart — the files are inert. Garbage-collect or ignore them (`wf mem-hygiene` lists them).

## Consequences to act on

1. **A fresh project starts memory-blind.** The bucket is keyed on *that repo's* path, so a new adopter has
   an empty bucket and none of the accumulated lessons. Seed it from git (`./init.sh --memory`).
2. **The slug is machine-specific** (the repo's absolute path with `/` → `-`). **Derive it; never hardcode
   it** — a hardcoded slug is one operator's machine presented as universal.
3. **Anything another stream must rely on belongs in git**, not the bucket: the bucket is unversioned,
   unreviewable, and local. Git = Tier A; the bucket = a thin shared cache; `STATE.md` = now.
4. **The index has a load cap** (~24 KB) and **truncates silently** over it — keep `MEMORY.md` a thin
   index, detail in topic files, cold entries in `ARCHIVE.md`.
