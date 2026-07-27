# UC-00 — Bootstrap the control plane in a fresh repo

**Actor:** operator + the first (SA) session. **Trigger:** a brand-new project wants a resilient
multi-session Claude Code setup. **Precondition:** a git repo exists; the framework dir has been copied in.
**Goal:** reach a green `wf doctor --compliance` + `wf smoke` — the operational-ready bar.

This is the *day-0* playbook (the step-by-step is in [`../QUICKSTART.md`](../QUICKSTART.md); this is the
use-case view with the why + the exit criteria). UC-01 onboards *additional* streams later; UC-00 is the
one-time stand-up.

## Steps

1. **Name the project.** `project.example.yaml` → `project.yaml`; set `project_name`, `hook_namespace`,
   `protected_paths`, and `decoupling_nouns` (your paths/stack/domain terms — this is what makes the core
   gate protect *your* project). — *why:* the core is project-agnostic and reads identity only from here.
2. **Declare streams.** `streams.example.yaml` → `streams.yaml`; keep SA (orchestrator, `can_merge: true`)
   on the main root; add one entry per stream with a distinct `lane`, `base`, and `governs:` charter.
3. **Create worktrees** for each non-SA stream (`git worktree add ../<name> -b <branch> origin/<base>`).
4. **Mint charters** from `_TEMPLATE.md` (one per stream); wire each via `governs:` in the registry.
5. **Install + generate.** `sync-hooks.sh` (hooks + `wf` → `~/.claude/hooks/<namespace>/`);
   `gen-config.py` (per-worktree `settings.json`, incl. SA-only merge scoping).
6. **Seed `STATE.md`** in each worktree (`**Stream:** <id>` header — the hooks + dispatch router read it).

## Exit criteria (the readiness bar)

- `wf doctor --compliance` → **exit 0** — every registered stream is present, its STATE-id matches the
  registry, and its `settings.json` matches `gen-config`.
- `wf smoke` → **green** — proves a blank host can stand up the whole substrate (doctor / dispatch /
  gen-config / loop / hooks) with generic config. This is the behavioral genericity gate.
- `wf decoupling-lint --zone core` → **exit 0** — no project nouns leaked into the framework core
  (relevant if you'll re-sync the framework via subtree; see E3).

## Notes

- **Launch each stream from ITS worktree dir** — identity = the `STATE.md` in the launch cwd. Launching from
  the wrong dir brings a stream up as the wrong identity (a known foot-gun).
- **SA merges** (post-review); all other streams are `can_merge: false` (enforced by `gen-config` on both the
  Bash and GitHub-MCP surfaces).
- Recovery drill once you're up: [`../DISASTER-RECOVERY.md`](../DISASTER-RECOVERY.md) (run `wf doctor` → SA
  bootstrap prompt reconstructs every stream).
