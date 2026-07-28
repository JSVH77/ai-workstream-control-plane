# UC-03 — Restart a live stream (wire it to the workflow; verify state retention)

**Scenario:** A stream's session is live but **predates** part of the workflow (it started before the current
hooks / settings / dispatch inbox), or it crashed. You want to **restart it** so it's properly wired to the
control plane — and confirm it **retains its latest state** across the restart.

**Actors:** **Operator** (you) · the **Stream** (the session being restarted) · **(auto)** (framework).

## Do the pre-workflow streams need a restart? — yes, with a nuance

- **What a restart gives them (needs restart):** the SessionStart **auto-behaviors** — injection of their
  *current* `STATE.md` + git orientation + last journal + their **dispatch inbox**, and pickup of the
  current hooks + generated `settings.json`. A session that started before those were finalized won't have
  them until it restarts.
- **What does NOT need a restart:** *using* the tools. A running stream can already `wf dispatch inbox|send`
  and `wf doctor` (the launcher is installed globally, branch-independent). So it can participate manually
  today; the restart just makes the auto-behaviors kick in.
- **It's safe** because **state is retained** (below) — a restart costs only the conversation transcript,
  not the working state.

## State retention — what survives a restart

Survives (re-assembled on restart): **`STATE.md`** (on disk in the worktree → injected as "what I was doing"),
**git** (branch + commits), the **journal**, the **dispatch inbox**, and the stream's **memory bucket**.
Lost: the **conversation transcript** (the turn-by-turn history) — but `PreCompact` backs it up to
`.claude/transcript-backups/` if you ever need it. **Recover the state, not the movie.**

> **Retention quality = `STATE.md` currency.** The restarted stream orients from `STATE.md`'s "## Active
> task" lead. If the stream kept it current, it resumes exactly where it was; if `STATE.md` is stale, the
> restart orients to the wrong point. Keeping `STATE.md` current is the stream's discipline.

## Sequence

| # | Actor | Step |
|---|---|---|
| 0 | **Operator (or SA)** | *(Optional pre-check)* `wf doctor` shows the stream's current task from its `STATE.md` — that's what the restart will inject. Confirm it's the state you expect to be retained. |
| 1 | **Operator** | In the stream's worktree, make sure its work is committed/pushed (so nothing un-captured is lost with the session). |
| 2 | **Operator** | Kill the stream's session; start a fresh Claude session in the **same worktree**. |
| 3 | **(auto)** | SessionStart injects the stream's `STATE.md` + git orientation + journal + **DISPATCH INBOX**; CLAUDE.md points it to `README.md`. |
| 4 | **Stream (new)** | Self-orients from `STATE.md` to its latest task; sees its inbox; resumes its own work. *(No bootstrap prompt needed — unlike SA in UC-02, a stream just resumes its own lane, it doesn't orchestrate others.)* |
| 5 | **Operator** | Verify (below). |

## Verification checklist (the "test" half)

- [ ] The restarted stream reports the **same active task** it had before (e.g. "PR #42, awaiting SA
      merge") — **state retained** from `STATE.md`.
- [ ] Its **DISPATCH INBOX** shows any queued messages (proves the SessionStart inbox wiring is live).
- [ ] `wf dispatch ack` / `wf doctor` work from its worktree.
- [ ] Its `.claude/settings.json` is the generated one (merge denied — it's not SA).

## Relationship to UC-02

UC-03 (restart a *stream*) and UC-02 (recover *SA*) use the **same mechanism** — SessionStart re-injects
`STATE.md` + `doctor` reconstructs. The difference: **SA** needs the bootstrap prompt because it
*orchestrates* the recovery of every other stream; a **stream** just resumes its own lane. Wire the streams
(UC-03) before testing SA recovery (UC-02).
