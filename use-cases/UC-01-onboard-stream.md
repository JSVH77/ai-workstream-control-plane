# UC-01 — Onboard a new dedicated stream via SA

**Scenario:** SA is live. You want a **new dedicated session with a specific purpose** (worked example: a
**CR** = code-review session), running inside the workflow as a first-class stream — with its own worktree,
scoped config, resilience hooks, dispatch inbox, and recovery.

**Actors:** **Operator** (you) · **SA** (the orchestrator session you talk to) · **(auto)** (framework).

**Principle:** you don't hand-wire the new session. You tell **SA the intent**; SA does the mechanical
onboarding (register → worktree → config → STATE → memory → kickoff prompt) and hands you back two things:
a **worktree path** and a **kickoff prompt**. You open the session and paste the prompt. Done.

## Sequence

| # | Actor | Step |
|---|---|---|
| 1 | **Operator → SA** | State the intent: **id** (must be registry-safe, e.g. `CR`), **purpose**, **lane** (what it owns / is allowed to touch — a reviewer is read-only), **base** branch, **model**, **can_merge** (streams = false; SA-only). *E.g. "Add a CR stream: deep methodology-aware code review, read-only, base main, no merge."* |
| 2 | **SA** | Register it in `config/streams.yaml` (the one source of truth), **including its `governs: charters/<id>.md` pointer**, → PR to `main` (and `integration` if it forks from there). **Operator merges.** |
| 2b | **SA** | **Author its charter** `charters/<id>.md` (same PR): the stream's *rulebook* — the authoritative domain artifacts it must **apply** (apply-authority, the dual of `lane`). Cite **tracked** anchors only (a `docs/*` path, a `file:line`, or the originating PR — never a per-worktree memory file). A stream isn't onboarded without one. See `charters/README.md`. |
| 3 | **SA** | Create the worktree: `git worktree add ../myproject-cr <base>`. |
| 4 | **SA** | Generate its scoped config: `wf gen-config --worktree myproject-cr` → writes `.claude/settings.json` (merge denied on Bash + MCP for a non-SA stream). Hooks are already installed globally. |
| 5 | **SA** | Write its `STATE.md` — identity/lane/base/purpose/first-task **+ a `## Governance` summary pointing to its charter** (terse; charter is SOT). **The `Stream:` id MUST equal the `streams.yaml` key** (or its dispatch inbox silently breaks — see UC-01 note). |
| 6 | **SA** | Seed the shared memory bucket **thin**: just this stream's operating playbook. Durable/shared knowledge stays in git. (Remember the bucket is SHARED across worktrees — spec §8 — so there is no per-stream bucket to seed.) |
| 7 | **SA** | Draft the **kickoff prompt** — the session's job in one paste: who it is, its lane, what it reviews, how it reports (via `wf dispatch`), and "read `README.md` + your STATE.md first." |
| 8 | **SA → Operator** | Hand over: **(a)** the worktree path, **(b)** the kickoff prompt. |
| 9 | **Operator** | Open a **new** Claude Code session in the worktree (`cd ../myproject-cr`, launch Claude), **paste the kickoff prompt**. |
| 10 | **(auto)** | SessionStart hook injects the session's `STATE.md` + git orientation + its **dispatch inbox**; CLAUDE.md's banner points it to `README.md`. The session self-orients as `CR`. |
| 11 | **Operator + SA** | **Verify** (the test): `wf doctor` shows `CR` registered + compliant; SA sends a probe — `wf dispatch send --from SA --to CR --type review_request --topic "..."`; the CR session sees it in its inbox, `wf dispatch ack`s it, and reports findings back via `wf dispatch send --to SA`. |

## Verification checklist (the "test" half)

- [ ] `wf doctor` lists `CR` under STREAMS, matched to `myproject-cr`, not `[!] NOT REGISTERED`.
- [ ] `CR`'s `.claude/settings.json` denies `gh pr merge` + the MCP merge tool (SA-only merge holds).
- [ ] Starting the CR session shows a `DISPATCH INBOX` section (hook + STATE-id resolve correctly).
- [ ] A `send → inbox → ack → report` round-trip works between SA and CR.
- [ ] `governs:` resolves + `charters/<id>.md` exists, cites tracked anchors, and STATE has a `## Governance` pointer (the charter/apply-authority layer, spec §3.8).

## Notes / gotchas

- **Id consistency (a real incident):** the `Stream:` id in `STATE.md` must be **byte-identical** to the
  `streams.yaml` key. A display-vs-key mismatch (e.g. `VL/VR` written where the key is `VLVR`) makes the
  stream's inbox come up empty even though envelopes exist — it fails *silently*. `wf doctor --compliance`
  now checks exactly this (spec §3.4 gate (2)); run it after onboarding.
- **What SA merges:** the `streams.yaml` PR (step 2). The new stream itself never merges.
- **Teardown:** to retire a stream — remove its `streams.yaml` entry (PR), `git worktree remove
  ../myproject-cr`, and delete its memory bucket. Its dispatch history stays in the append-only log.
