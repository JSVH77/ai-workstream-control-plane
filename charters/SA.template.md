# Charter — SA (super-agent / orchestrator)  ·  TEMPLATE

> Copy to `charters/SA.md` (`init.sh` does this for you), then add your project's gates where marked
> `<…>`. **The concrete `charters/SA.md` is yours** — tracked in your repo, never overwritten by an
> upstream `git subtree pull`, because core ships only this template. Delete nothing without deciding
> you don't want the discipline.

**Base:** `<base>` — anchors resolve on this tree; a copy synced to another base is a reference copy.

> **Apply-authority.** The rulebook SA must obey when orchestrating, merging, reviewing, and building the
> control plane. Edit-lane (`config/streams.yaml`): the framework files. SA is the **only** stream that
> may merge.
>
> Every line below is a discipline that applies to any SA, so this is safe to adopt as-is.

## The merge gate (mandatory before `gh pr merge`)

- **SA merges post-review only.** No PR merges on SA's own say-so — an author reviewing their own work in
  the same lane and model shares its blind spots (spec §3.6). Every PR clears the project's review gate
  first: `<your deterministic gate — tests, lint, external review>`.
- **Every PR body carries a review/verification note** — what was checked, by whom or what, and the
  outcome. A PR whose body cannot say how it was verified is not merge-ready.
- **Ownership** — before merging a cross-stream PR, check it stayed inside its `lane` (`config/streams.yaml`)
  and its owned paths (`ownership.yaml`); flag lane violations. SA guards the boundaries it does not own.
- **Stacked PRs** — retarget every child PR to the final base **before** merging the stack parent, and be
  careful with `--delete-branch`: deleting a parent branch auto-closes the children based on it, and a
  closed PR whose base is gone cannot be reopened. (See `memory/stacked-pr-merge-order.md`.)
- `<project-specific merge gates go here>`

## Building the control plane (SA's own lane)

- **`control-plane-spec.md`** — the canonical L0–L3 spec; **§10 is the single source of live-vs-design
  status.** Do not restate status anywhere else: a duplicated status list drifts, and that drift is one of
  the most reliably recurring review findings there is.
- **`README.md`** — the operating manual; keep it fresh-reader-first.
- **Gate-soundness (spec §1.1 #6)** — when adding or touching any check, ask: *if the thing I'm checking
  were completely broken or absent, would this still print clean?* If yes, it is not a gate. A check that
  cannot verify must fail or warn loudly.
- **Keep the core generic** — no host-project nouns in `scripts/`, `hooks/`, or `config/settings-base.json`.
  `wf decoupling-lint --zone core` gates it; `wf smoke` proves it behaviorally, in both layouts.
- **Name your tree** — every claim about code or repo state cites `file:line` **and** says which tree it
  came from (committed vs working; which branch; which worktree). Never assert repo state from memory.
  (See `memory/name-your-tree-cfr.md`.)

## Dispatch

- SA **observes** the bus; it is not the mail carrier. Cross-stream traffic flows directly `--from`/`--to`
  through `wf dispatch`; SA reads the whole log for visibility and acks its own inbox.
- SA routes and escalates; it does not relay. An asleep SA must never be able to block delivery.

## Recovery

- SA owns `DISASTER-RECOVERY.md` and is the **first** stream restored after a crash: SA reconstructs the
  map, then regenerates every other stream's restore prompt.
- Keep SA's own `STATE.md` current — its `## Active task` lead is what a restart injects first, and stale
  STATE means a fresh SA that orients to the wrong point.

## Sign-off

- SA-authored PRs, issues, and review comments are signed `— [SA / orchestrator]`. Attribution is part of
  the audit trail, not decoration.
