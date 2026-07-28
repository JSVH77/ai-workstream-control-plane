# SA bootstrap — bring up the orchestrator for THIS repo (portable startup kit)

The **portable SA session startup**: the way you bring up the orchestrator (SA) role in *any* repo that
adopts this control plane. Generalized from a real multi-stream project's SA discipline.

Use it once, at first bring-up. After `wf sync-hooks` has installed the SessionStart hook, every later
session auto-injects `STATE.md` + git orientation + the dispatch inbox, so SA re-orients without a prompt.

## Prerequisites

The framework is installed and `./init.sh` has run (see [`QUICKSTART.md`](QUICKSTART.md)). At minimum
`config/project.yaml`, `config/streams.yaml`, and a root `STATE.md` naming `**Stream:** SA` must exist —
that token is the dispatch router key, and it must match the registry key byte-for-byte.

> ### ⚠ Bring SA up in a session started AFTER `gen-config`
>
> **Settings load at session START.** Whichever session ran `init.sh` is still on your global permissions —
> it has no project floor (`rm -rf /`, force-push, `sudo` denies) and no hook wiring, and nothing it does
> later can load them. The committed baseline `.claude/settings.json` covers a fresh *clone*; it cannot
> retrofit a session that was already running.
>
> So the bring-up order is: `init.sh` → `sync-hooks` → `gen-config` → **restart** → paste the prompt below.
> Started SA in the pre-floor session? Finish the setup, then restart and re-paste. A quick check that the
> floor is live: SA should be denied `sudo` and `git push --force`.
>
> Personal per-worktree allows belong in `.claude/settings.local.json` (gitignored, never touched by
> `gen-config`) — not in `settings.json`, which `gen-config` regenerates.

## The launch prompt

Paste into a fresh Claude Code session started in the repo root. Replace `<PROJECT>`; drop the `wf` names
you haven't enabled.

> You are **SA (super-agent / orchestrator)** for the **`<PROJECT>`** project.
> Your job: coordinate streams, own the control-plane framework, and merge PRs post-review (SA-only).
> On start: read `STATE.md` (your live spine), your charter `charters/SA.md`, `config/streams.yaml`
> (the registry), and `control-plane-spec.md` (the model; **§10 = the live-vs-design source of truth**).
> Your tools are `wf <dispatch|doctor|gen-config|mem-hygiene|loop|pre-push|decoupling-lint|smoke|sync-hooks>`.
> Disciplines: **merge only post-review**; every PR body carries a review/verification note; **name your
> tree** on any repo-state claim; sign off SA-authored PRs/issues/comments with `— [SA / orchestrator]`.
> **First task: <the concrete task>.**

Then, in the session:

```bash
wf doctor                 # what the topology actually is, vs the registry
wf doctor --compliance    # the readiness gate — exits non-zero on any shortfall
```

## Why the prompt says what it says

Each clause is load-bearing; none is decoration.

- **"read STATE.md first"** — STATE is Tier C, the volatile "now". Its `## Active task` lead is what a
  restart orients from. Everything else is reconstructible; the current task is not.
- **"§10 = the live-vs-design SOT"** — the spec describes more than is built. A single status section
  prevents the most reliably recurring failure in this repo's own history: a second status list that
  drifts. Do not restate status elsewhere.
- **"merge only post-review"** — an author reviewing their own work in the same lane and model shares its
  blind spots. `can_merge` in the registry enforces SA-only merge on both the Bash and MCP surfaces; the
  *discipline* is what stops SA from merging its own unreviewed work.
- **"name your tree"** — every repo-state claim says which tree it came from (committed vs working, which
  branch, which worktree). See `memory/name-your-tree-cfr.md`.
- **"sign off"** — attribution is part of the audit trail. In a multi-stream setup an unsigned comment is
  an unattributable one.

## Seeding SA's memory (do not skip)

A fresh adopter's vendor memory bucket is **empty** — it is keyed on *this* repo's path, so a new SA starts
with none of the accumulated operating lessons, and no amount of prompting recovers what was never there.

```bash
./init.sh --memory     # copies memory/*.md + MEMORY.template.md into the bucket
wf mem-hygiene         # confirm: index present, pointers resolve, under the load cap
```

`memory/` holds the portable disciplines (name-your-tree, gate-soundness, worktree resolution, stacked-PR
order, review monitors, the memory-scoping model, the situational-awareness format). **Git is the durable
source of truth; the bucket is a thin cache** — improve a lesson in `memory/`, then re-copy.

## Recovering an SA that died

Different situation, different document: [`DISASTER-RECOVERY.md`](DISASTER-RECOVERY.md) (run `doctor`,
paste the recovery bootstrap prompt, reconcile every stream, regenerate their restore prompts). This file
is for a *first* bring-up; that one is for a crash. See also
[`use-cases/UC-02-recover-sa.md`](use-cases/UC-02-recover-sa.md).
