# UC-02 — Recover SA after a crash (the first disaster-recovery action)

**Scenario:** SA (the orchestrator session) died — crash, closed terminal, or compaction wiped its context.
You want to bring **SA** back online. This is the **first** DR action because SA is the session that
reconstructs the map and regenerates every *other* stream's restore prompt: recover SA → SA recovers the rest.

**Actors:** **Operator** (you) · **SA** (the fresh session you're restoring) · **(auto)** (framework).

**Why it works without any live SA to help you:** the recovery inputs live *outside* the dead session —
in git (the framework dir, `DISASTER-RECOVERY.md`, the spec), in the gitignored per-worktree `STATE.md` +
journal, and in SA's file-memory bucket. A fresh session re-assembles them. **Command-first, prompt-second:**
`doctor` gathers the facts deterministically; the bootstrap prompt makes the new SA reason over them.

## Sequence

| # | Actor | Step |
|---|---|---|
| 1 | **Operator** | In the **main root** (`<dev-root>/myproject`), start a fresh Claude Code session — this becomes the new SA. |
| 2 | **(auto)** | SessionStart hook injects SA's `STATE.md` (its "what was I doing") + git orientation + last journal breadcrumbs + its dispatch inbox. CLAUDE.md's banner points it to `README.md`. |
| 3 | **Operator** | Open `DISASTER-RECOVERY.md`, copy the **SA bootstrap prompt** (Step 2 there), and paste it into the session. *(You don't have to remember it — it's in the repo.)* |
| 4 | **SA (new)** | Runs the bootstrap: reads its **role memory** (`feedback_sa_role_pda_probe_workflow.md` + the control-plane pointer) → runs **`wf doctor`** → reads `control-plane-spec.md` + its `STATE.md` → **reconciles** each stream's worktree/branch/drift vs. what STATE + open PRs say; flags anything unexpected. |
| 5 | **SA (new)** | Reports the reconstructed state + (for full recovery) emits a restore prompt for each other stream. Does **not** act on stream work until you confirm — it recovers the *map* first. |

## Verification checklist (the "test" half)

- [ ] The fresh session **self-identifies as SA** (from STATE + role memory) and knows its job.
- [ ] `wf doctor` reconstructs **every** registered stream with its branch + current task.
- [ ] SA correctly states the **current phase / open work** (from STATE.md's lead + open PRs) — i.e. STATE
      was current enough to orient from.
- [ ] SA can produce a restore prompt for at least one other stream from the report.

## Notes / gotchas

- **STATE.md currency IS the recovery quality.** The lead of SA's `STATE.md` "## Active task" is the primary
  "what was I doing" signal — keep it current (SA updates it as phases change). A stale STATE = a fresh SA
  that orients to the wrong point. (Journals + `doctor` fill the rest, but STATE is the summary.)
- **What the fresh SA does NOT have:** the dead session's turn-by-turn conversation. It reconstructs the
  *state*, not the *transcript* (the `PreCompact` backup preserves the raw transcript if you truly need it —
  `.claude/transcript-backups/`). Recover the map, not the movie.
- **Running the test ends the current SA session** — you're deliberately killing it to prove recovery. Do it
  when SA's STATE + any in-flight commits are pushed/clean, so nothing un-captured is lost with the session.
- Full team recovery then continues per `DISASTER-RECOVERY.md` Step 3 (operator re-seats each stream with
  the prompt SA generated).
