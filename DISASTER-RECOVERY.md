# Disaster Recovery — AI Workstream Control Plane

**Command-first, prompt-second** (spec §3.4). After a crash or compaction that wiped in-session state,
recovery is: run the deterministic `doctor` script → paste the SA bootstrap prompt, which reasons over the
report and regenerates each stream's restore prompt. *Script is substrate; prompt is UX.*

> Why it works with no live session to help you: every recovery input lives **outside** the dead session —
> in git (this framework + the spec), in the gitignored per-worktree `STATE.md` + journal, and in the shared
> memory bucket. A fresh session re-assembles them.

## Step 1 — get the recovery report

Start a Claude Code session in a worktree that has the framework checked out (SA's main root is the normal
choice) and run:

```bash
wf doctor           # human report
wf doctor --json     # machine-readable (for tooling)
```

This is **read-only**. It reports: every stream (target registry vs live `git worktree list`), each
worktree's branch / HEAD / drift-vs-origin-base / dirty count / STATE task / last journal line; open PRs;
stashes (including forgotten WIP); and runtime state (pending dispatch envelopes, loop leases).

Run `git fetch --all` first if you need fresh drift numbers — `doctor` will not fetch for you.

**Read the report honestly.** `doctor` distinguishes *unavailable* from *empty*: `OPEN PRs: [!] UNAVAILABLE`
means `gh` failed, **not** "no open PRs". A recovery tool that renders unreachable state as clean is worse
than one that says nothing (spec §1.1 #6).

## Step 2 — restore SA: paste this bootstrap prompt into the session

Parameterise `<PROJECT>`; adjust the memory names if your bucket uses different ones.

```
You are SA (super-agent / orchestrator) for <PROJECT>. We are recovering from a crash/compaction.

1. Read your operating memories in full — your role/playbook memory and the control-plane pointer — from
   the vendor memory bucket for this repo (it is keyed on the MAIN worktree's absolute path; derive it,
   don't assume a path). If the bucket is empty, seed it: `./init.sh --memory`.
2. Run `wf doctor` and read the recovery report.
3. Read `control-plane-spec.md` (the canonical L0-L3 model; §10 = what is actually live) + your STATE.md
   + your charter `charters/SA.md`.
4. Reconcile: for each stream in the report, confirm its worktree/branch/drift against what its STATE.md
   and open PRs say. Flag any drift, unexpected dirty state, unregistered worktrees, or stale stashes —
   and any stream the report could not resolve (absent/ambiguous worktrees are failures, not blanks).
5. Emit a restore prompt for each OTHER stream for the operator to paste into that stream's terminal —
   each naming the worktree path, lane, base, current branch + open work (from the report), its charter,
   and the merge rule (SA-only, post-review).

Then report the reconstructed state and await direction. Do NOT act on any stream's work until the
operator confirms; recover the map first.
```

## Step 3 — operator re-seats the streams

SA hands you one restore prompt per stream; paste each into its terminal (`cd` to that worktree first).
Each stream's SessionStart hook already injects its STATE spine, so the prompt is confirmation and
orientation, not a cold start.

**Launch each stream from ITS worktree dir.** Identity comes from the `STATE.md` in the launch cwd — start
a session in the wrong directory and it comes up as the wrong stream.

## Notes

- `doctor` gathers facts; SA reasons over them. Neither mutates stream work.
- **What a fresh SA does *not* have:** the dead session's turn-by-turn conversation. It reconstructs the
  *state*, not the *transcript* — the `PreCompact` backup preserves the raw transcript in
  `.claude/transcript-backups/` if you truly need it. **Recover the map, not the movie.**
- **STATE.md currency IS recovery quality.** The `## Active task` lead is the primary "what was I doing"
  signal. A stale STATE means a fresh SA that orients to the wrong point.
- If the framework isn't on the branch you land on, `wf` still works — it resolves the tools from the main
  worktree via git-common-dir, independent of your branch.
- The resilience hooks (`~/.claude/hooks/<hook_namespace>/`) already re-inject per-worktree STATE at
  SessionStart. `doctor` + this runbook are the *cross-stream* layer on top of that per-worktree layer.
- Related playbooks: [`use-cases/UC-02-recover-sa.md`](use-cases/UC-02-recover-sa.md) (this drill as a
  test case) and [`use-cases/UC-04-restore-readiness-dryrun.md`](use-cases/UC-04-restore-readiness-dryrun.md)
  (verify a stream *would* restore, before you risk restarting it).
