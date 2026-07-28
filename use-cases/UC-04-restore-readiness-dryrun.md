# UC-04 — Dry-run a stream's restore-readiness (before a risky restart)

**Scenario:** You're about to restart a live stream (UC-03), but a restart is a **gamble** — if the
stream's restore path is broken (hooks unwired, STATE stale, id mismatch), you find out *after* you've
already lost the running session. This case verifies the stream **would** restore — with **zero risk**,
**without** actually restarting it.

**Actors:** **Operator** (you) · **SA** (the orchestrator) · **target stream** (the one under test).

**Principle:** a stream can **audit its own restore path** by running the same mechanisms `SessionStart`
would — but on demand, in the *live* session. SA sends a `self_check` dispatch; the stream runs the audit
(including *simulating* the SessionStart hook), and reports `PASS` / `GAPS`. Fix any gap **before** the
real restart. A dry run is strictly better than restart-and-hope: no session lost, and it routinely
catches stale assumptions (see Notes).

## Sequence

| # | Actor | Step |
|---|---|---|
| 1 | **SA → target** | Send the **self-check dispatch** (template below), parameterised for the target's id / worktree / current task. `wf dispatch send --from SA --to <ID> --type self_check --topic "…" --refs restore-dryrun`. |
| 2 | **Operator** | Nudge the **live** target session: *"check your dispatch inbox and run the restore-readiness self-check."* (A dry run fires **no** SessionStart event, and the target may not auto-surface the inbox — so nudge it explicitly.) |
| 3 | **target** | Run the 6 checks (template). Crucially, **simulate** the restore: `bash ~/.claude/hooks/<hook_namespace>/session-start.sh` — confirm it emits STATE + git orientation + inbox **without** restarting. |
| 4 | **target → SA** | Report: `wf dispatch send --from <ID> --to SA --type self_check_result --topic "<PASS \| GAPS: specifics>" --refs restore-dryrun`, then `wf dispatch ack` the request. |
| 5 | **SA** | Read the verdict. **PASS** → safe to run UC-03 (actual restart). **GAPS** → fix first (usually `wf gen-config --worktree <WT>` + `wf sync-hooks`), then re-run this dry run. |

## The self-check dispatch template

Parameterise `<ID>` / `<WORKTREE>` / `<TASK>` and send as `--type self_check`:

> DRY-RUN restore-readiness self-check — do **NOT** restart; **audit** whether you would survive a restart,
> then report. Run each:
> 1. **HOOKS** — `ls ~/.claude/hooks/<hook_namespace>/` present? AND does your worktree `.claude/settings.json`
>    actually **wire** SessionStart/Stop/PreCompact? (If unwired you will **not** auto-restore — fix:
>    `wf gen-config --worktree <WORKTREE>` + `wf sync-hooks`.)
> 2. **SIMULATE** — `bash ~/.claude/hooks/<hook_namespace>/session-start.sh` — does it emit your STATE + git
>    orientation + DISPATCH INBOX?
> 3. **STATE** — `STATE.md` present + current (task = `<TASK>`)? Stream id **exactly** `<ID>` (== registry key)?
> 4. **DOCTOR** — `wf doctor` — `<ID>` registered, matched to `<WORKTREE>`?
> 5. **INBOX** — `wf dispatch inbox --stream <ID>` — do you see this envelope? (proves delivery)
> 6. **GOVERNANCE** — STATE has a `## Governance` summary + is `charters/<ID>.md` reachable on your base?
>
> Report `--type self_check_result --topic "<PASS | GAPS: specifics>" --refs restore-dryrun`, then ack this.

## Verification checklist (the "test" half)

- [ ] Target reports a `self_check_result` with an explicit **PASS (n/6)** or an enumerated **GAPS** list.
- [ ] Check 1 (hooks) is answered from the **actual** `.claude/settings.json`, not from a STATE claim.
- [ ] Check 2 (simulate) shows `session-start.sh` really emits STATE + inbox — the load-bearing proof.
- [ ] Any stale STATE/doc claim discovered is **corrected** as part of the run (see Notes).
- [ ] On **GAPS**: the fix is applied and the dry run re-run to green **before** any real restart (UC-03).

## Notes / gotchas

- **What a real run showed (origin project):** PASS 6/6 — hooks wired, `session-start.sh` emitted
  correctly, STATE current, id matched, inbox delivered, governance present + charter reachable. The run
  also **falsified a stale assumption**: the stream's STATE claimed *"NO SessionStart hooks"* — wrong; they
  were wired. The stream corrected its own STATE. Without the dry run it would have gone into a restart
  expecting a gap that didn't exist (or "fixed" a non-problem). That self-correction is the whole value:
  **a dry run tests the doc as well as the machinery.**
- **Dry run ≠ restart.** No SessionStart event fires during a dry run, so the target must be nudged to check
  its inbox (step 2). The simulate step (`session-start.sh`) is what stands in for the real event.
- **Base currency:** a stream's *current feature branch* may lag its base, so `charters/<ID>.md`
  can be verified "on base" (check 6) yet not be in the working tree until the next branch off the updated
  base. That's expected (charters are base-scoped) — the `## Governance` STATE summary arms governance
  regardless of branch.
- **Complements UC-03:** UC-04 is the *pre-flight*; UC-03 is the *flight*. Run UC-04 whenever a restart is
  risky (pre-workflow stream, uncertain hook wiring, long-lived session you don't want to lose).
