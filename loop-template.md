# Loop contract template (control-plane spec §3.5)

Copy this to `loops/<name>.md`, fill the frontmatter, and drive it with **`wf loop`**. Looping is
safe **only** with a hard, machine-checkable exit contract owned by something *outside* the agent — this
file is that contract; `wf loop` (`scripts/loop.py`) is the deterministic engine that enforces it. **The
loop produces a PR; it NEVER merges** (SA-only merge, post-review, stays).

> **If the exit can't be a command that returns 0/1, don't loop it.** Best fits: fix-until-green engine
> tasks, behavioral probe loops. Worst fit: open-ended design.

```markdown
---
task: "<one line: what 'done' means>"
exit_cmd: "<a shell command returning 0 when DONE, non-0 otherwise>"   # the independent oracle
max_iters: 8                 # BUDGET — hard iteration cap
max_unchanged: 2             # stop after N iters with a flat diff / same failing check
scope: ["src/core/**"]       # globs this loop may touch; anything else trips the SCOPE BRAKE
scope_slack: 0               # files allowed outside scope before braking
exit_timeout_s: 600          # kill a hung exit_cmd
cost_note: "~$X/iter; hard cap N iters"   # BUDGET — cost, for the operator
---
Acceptance criteria in prose; links to the ticket / acceptance predicate; anything the worker needs.
```

## The four guardrails (required — `wf loop` enforces 2–4; you own 1)

1. **Independent oracle (you).** `exit_cmd` must be graded from **outside the edited lane** — e.g. a
   test suite, an integration check, a behavioral predicate. A loop that edits *and* grades the same lane
   reward-hacks. The engine can't verify "outside the lane" for you; the reviewer checks it.
2. **Max unchanged iterations.** Flat diff (or the same failing check) `max_unchanged` times → auto-stop
   (the worker is stuck).
3. **Lease + heartbeat.** `wf loop start` writes a lease (`.workflow-runtime/leases/<stream>.json`) with
   owner, task, exit_cmd, budget, started/heartbeat/iteration; `tick` heartbeats. `doctor` surfaces stale
   leases for crash recovery + cleanup. One live loop per stream.
4. **Scope-expansion brake.** Changes to files outside `scope` (beyond `scope_slack`) → stop and ask the
   operator, rather than silently sprawling.

## How to run it

```bash
wf loop start --contract loops/<name>.md   # validate + acquire the lease (refuses if one is live)
# then, each iteration:
#   <do one iteration of work>                       # the agent, or a `ralph` bash loop, does the work
wf loop tick                                         # heartbeat; run exit_cmd; enforce guardrails; verdict
wf loop status [--all]                               # inspect;  wf loop release  when done/PR'd
```

**`tick` exit codes** (so a `ralph` bash loop can drive it):

| code | meaning |
|---|---|
| `0`  | **CONTINUE** — exit not met, no guardrail tripped |
| `10` | **STOP: exit met** ✅ — open a PR (never merge) |
| `20` | STOP: budget (`max_iters`) |
| `21` | STOP: stuck (`max_unchanged`) |
| `22` | STOP: scope brake |
| `23` | STOP: oracle unavailable — `exit_cmd` couldn't run (timeout / missing binary). Fails **closed**, never "continue" |

```bash
# ralph pattern — an external while-loop; the engine owns the exit decision
wf loop start --contract loops/fix.md
while true; do
  <invoke the worker for one iteration>   # e.g. a claude/codex CLI call with the task
  wf loop tick || break                   # non-zero => stop (done or a guardrail); reason is printed
done
wf loop status && wf loop release
```

An **agent** worker reads the printed verdict instead of the exit code; either way the *engine*, not the
agent, decides continue/stop — that's the whole point.
