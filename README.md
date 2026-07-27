# AI Workstream Control Plane

**A reusable control plane for running several long-lived Claude Code sessions (streams) in parallel on one
repository — without losing state to crashes, colliding on files, or drifting apart.**

Extracted from the AsterClaude project's `workflow/` (design record: that repo's issues #205 / #237 / #238).
This is the **project-agnostic** framework; a host project adds only its overlay (`config/streams.yaml`,
`config/project.yaml`, `charters/*`, `ownership.yaml`).

> **Status: SEEDING (E2 extraction in progress).** This repo currently holds the bootstrap/handoff only.
> The generic core + templates are being extracted from AsterClaude — see [`SA-BOOTSTRAP.md`](SA-BOOTSTRAP.md)
> for the extraction task list and the layout decision to resolve.

## What it gives you (the seven pieces)
1. **Resilience** — SessionStart/Stop/PreCompact hooks: re-inject each stream's `STATE.md` + git orientation
   + dispatch inbox on restart; journal breadcrumbs; transcript backups.
2. **Isolation & governance** — one git worktree per stream, scoped to a file **lane** (`ownership.yaml`,
   edit-authority) + a **charter** per stream (apply-authority).
3. **Coordination** — an append-only cross-stream dispatch bus (`send`/`inbox`/`watch`/`ack`/`log`/`show`).
4. **Consistency** — a stream registry + config generator (`gen-config`) → per-worktree `.claude/settings.json`.
5. **Recovery** — `doctor` (health/topology + `--compliance` gate) + a disaster-recovery runbook.
6. **Deterministic gates** — a review-findings ledger + `pre-push` guard + `decoupling-lint` (keep host nouns
   out of the core).
7. **Safe autonomous loops** — a loop-contract engine (`wf loop`): fix-until-green behind an independent
   oracle + guardrails; opens a PR, never merges.

## Quickstart
See [`QUICKSTART.md`](QUICKSTART.md) *(arrives with the extraction)*. TL;DR once extracted: copy
`config/*.example.yaml` → real configs, mint charters, `sync-hooks`, `gen-config`, then validate with
`wf doctor --compliance` + `wf smoke`.
