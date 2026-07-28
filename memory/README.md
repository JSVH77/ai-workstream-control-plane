# `memory/` — portable discipline memories (the memory kit)

A fresh adopter of this framework starts **memory-blind**. The vendor auto-memory bucket is keyed on the
repo's absolute path (`~/.claude/projects/<main-worktree-path-slug>/memory/`), so a new project's bucket is
**empty** — none of the accumulated operating lessons are there, and nothing carries them over.

These files are the fix: the subset of operating disciplines that apply to **any** framework-adopting SA,
versioned in git (Tier A) and copied into the bucket on bootstrap:

```bash
./init.sh --memory       # copies these + MEMORY.template.md -> your bucket (idempotent, never overwrites)
```

**Git is the durable source of truth; the bucket is a thin cache.** If you improve one of these lessons,
improve it *here* and re-copy — an edit made only in the bucket is unversioned, unreviewable, and lost on
the next machine.

## What's here (and what's deliberately not)

Each file is one discipline, in the vendor bucket's frontmatter format, with the incident that produced it.
They are **generic**: no host project's nouns, paths, or domain methodology. The origin project's
*project* and *methodology* memories stayed behind — they would be noise (at best) in your bucket.

| File | The discipline |
|---|---|
| `name-your-tree-cfr.md` | every repo-state claim names its tree (committed vs working vs which worktree) |
| `gate-soundness.md` | a check that cannot verify must fail loudly — silence is never a pass |
| `worktree-resolution-canonical-path.md` | resolve streams → worktrees by canonical path, never by basename |
| `stacked-pr-merge-order.md` | retarget children before merging a stack parent; `--delete-branch` auto-closes them |
| `external-review-monitor.md` | how to arm a review-watching monitor so it actually fires (id-baseline, body-filter) |
| `vendor-memory-is-base-project-scoped.md` | one shared bucket per repo; per-worktree buckets are inert |
| `situational-awareness-format.md` | the default shape for "where are we?" — tree + status markers + gated/buildable |

Keep the bucket's `MEMORY.md` index thin (see `../MEMORY.template.md`): it loads every session under a
~24 KB cap and **truncates silently** over it.
