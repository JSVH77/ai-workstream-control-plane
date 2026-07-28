# Memory index

<!--
  TEMPLATE — `init.sh --memory` copies this to your vendor bucket as MEMORY.md:
      ~/.claude/projects/<main-worktree-abs-path-with-slashes-as-dashes>/memory/MEMORY.md
  (Derive that slug from your repo path; it is machine-specific — never copy someone else's.)

  THIS FILE IS LOADED INTO EVERY SESSION, under a ~24 KB cap. Over the cap it TRUNCATES SILENTLY:
  you lose recall with no error and no warning. So it is an INDEX, not a knowledge base.

  Rules that keep it working:
    - ONE line per entry, under ~200 chars: `- [name](file.md) — the hook, in a few words`
    - Detail lives in the topic file, never here.
    - Cold entries move to ARCHIVE.md (same dir) — that tier is not loaded.
    - Every file in the bucket should have a pointer here; every pointer should resolve to a file.
      `wf mem-hygiene` reports both halves (ORPHANS = file with no pointer, DANGLERS = pointer with no file)
      plus your current cap %.
    - This is Tier B: a shared, unversioned, machine-local cache. Anything another stream must RELY on
      belongs in git (Tier A). What you're doing right now belongs in STATE.md (Tier C).
-->

## Operating disciplines (portable — shipped with the control plane)

- [name-your-tree-cfr](name-your-tree-cfr.md) — every repo-state claim names its tree: committed vs working, which branch, which worktree.
- [gate-soundness](gate-soundness.md) — a check that can't verify must fail loudly; silence is never a pass.
- [worktree-resolution-canonical-path](worktree-resolution-canonical-path.md) — resolve stream → worktree by canonical path, never by basename.
- [stacked-pr-merge-order](stacked-pr-merge-order.md) — retarget children before merging a stack parent; `--delete-branch` auto-closes them.
- [external-review-monitor](external-review-monitor.md) — filter review polls by body + baseline on comment id, or the monitor never fires.
- [vendor-memory-is-base-project-scoped](vendor-memory-is-base-project-scoped.md) — one shared bucket per repo; per-worktree buckets are inert.
- [situational-awareness-format](situational-awareness-format.md) — default shape for "where are we": tree + markers + gated-vs-buildable.

## Project knowledge

<!-- Your project's own memories go below. Suggested prefixes, matching what mem-hygiene expects:
     project_*  = what we're building / decisions / findings
     feedback_* = how to work here (corrections + confirmed approaches)
     reference_*= pointers to external resources (dashboards, tickets, deploy targets)          -->

- *(none yet)*

## Archive

Cold entries live in [ARCHIVE.md](ARCHIVE.md) — present but **not** loaded each session. Move an entry
there rather than deleting it: the cap is about what loads, not about what you keep.
