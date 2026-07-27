# AI Workstream Control Plane — Specification

**Status:** ACTIVE — the L0 runtime + L1 control plane (registry, ownership, config generator, dispatch bus, doctor, loop engine, DR) are implemented; higher layers remain design. **§10 is the authoritative live-vs-design split.**
**Owner:** SA (the orchestrator stream of whichever project adopts this).
**Origin:** extracted from a real multi-stream project's `workflow/` directory after two crashes proved the discipline was the product. The host-specific overlay was left behind; what remains here is the project-agnostic core.

> **Read this before any framework change.** This document is the canonical source of truth for how
> multiple long-lived AI sessions (streams) survive crashes/compaction and coordinate.

---

## 0 · Why this exists

Long-lived AI coding sessions lose their context — to a crash, a closed terminal, or compaction. When several such sessions work one repository in parallel, that loss compounds: state disappears mid-task, sessions collide on files, and nobody can say who was doing what. Recovering means manual git and file archaeology.

That experience produced this framework. The real product is **not** "multi-agent workflow" in the abstract — it is a **resilience and control-plane discipline for long-lived AI workstreams**: write state continuously, re-inject it on resume, separate sessions by file lane, coordinate through an auditable queue, and turn the recurring failures into gates.

**Naming:** this is a **control plane**, not an "SDLC framework." The process/SDLC layer sits *on top* of it.

---

## 1 · The layer model (the spine)

Four layers, each with a distinct concern. Keep them separate; do not let a higher layer's assumptions leak down.

| Layer | Concern | Artifacts |
|---|---|---|
| **L0 — Runtime substrate** | Local continuity: survive crash/compaction | worktrees, hooks, `STATE.md` spine, journals, transcript backups, tracked/runtime split |
| **L1 — Control plane** | Coordination + operator-visible control | stream registry, ownership map (edit-authority), charters (apply-authority), dispatch queue, recovery report, loop contracts, review learning loop, config generator, attribution |
| **L2 — Process model** | What stages work moves through | the host project's own pipeline/ticket model — **out of scope for this framework** (§6) |
| **L3 — Provider adapters** | Isolate vendor-specific glue | Claude Code hooks, `/model` ids, MCP wiring, memory-loader quirks |

### 1.1 Design principles
1. **File-first + native hooks + git.** No GUI orchestrators, no dependence on experimental multi-agent runtimes (weak crash recovery is the #1 pain), no heavy swarm infra.
2. **Git is the only authoritative shared store.** Vendor memory is base-project-**shared** but **local + unversioned** (§8); it is neither versioned nor reviewable. Cross-stream *authoritative* truth lives in git.
3. **Write continuously + re-inject on resume.** The resilience contract (§2).
4. **Keep the file/git layer pure; quarantine vendor glue into L3.** A future provider = a new adapter, not a rewrite. Don't build the abstraction yet — just don't contaminate the pure layer.
5. **Deterministic where it counts.** Recurring failure modes graduate from prose guidance → mechanized gates (the review learning loop, §3.6).
6. **A check that cannot verify must fail loudly.** Silence is never a pass. Any guard, gate, or report that could not actually evaluate its subject — an absent worktree, an unresolvable ref, a swallowed subprocess error — must warn or exit non-zero, never print clean. (*gate-soundness*; it is the class that most often makes a green build a lie.)

### 1.2 Tracked vs. runtime — the hard split
- **The framework directory** — *tracked* assets: this spec, README, schemas, scripts, hooks, templates, charters, recovery procedures. Reviewable, versioned, shared via `.git`.
- **`.workflow-runtime/`** — *gitignored* live state: dispatch queue, journals, checkpoints, heartbeats, restore snapshots, per-run loop artifacts. Operational exhaust, never committed.

Rationale: runtime state in tracked paths creates repo churn, merge noise, accidental secret leakage, misleading history, and shared-file conflicts for things that are exhaust, not durable knowledge.

**Corollary — the substrate must be a committed revision, not a live edit.** `wf` resolves the tools from the main worktree's working copy, so an uncommitted edit there would become globally live for every stream before review. `wf` therefore **refuses to run** with uncommitted changes under the framework's `scripts/`, `config/`, or `hooks/` (compiled bytecode excepted — that is an artifact of running the tools, not an edit to them).

### 1.3 Installation layouts (both supported, neither assumed)
The framework may live either **flat** (it *is* the repo: `<repo>/scripts/`, `<repo>/config/`) or **vendored** under any prefix via `git subtree --prefix=<dir>` (`<repo>/<dir>/scripts/`). Nothing in the core may hardcode either shape: tools resolve the framework dir **structurally** — the directory containing `scripts/` — and the repo root via `git rev-parse --show-toplevel`, never by counting parent directories. `scripts/_cp_paths.py` is the single resolver; `wf smoke` stands the substrate up in **both** layouts, so this is a gate rather than a claim.

---

## 2 · L0 — Runtime substrate

### 2.1 Worktree-per-stream
Each stream is a git worktree = a fixed directory bound to a branch **slot** (the worktree persists; the branch rotates per task). Streams are separated by **file scope (lane)**, not by base branch — multiple streams may share the same base.

| Stream | Worktree | Lane | Base branch |
|---|---|---|---|
| **SA** (orchestrator) | `<repo>` (main root) | the control plane, cross-cutting reads | main |
| **S1** (e.g. frontend) | `<repo>-fe` | `src/frontend/**` | main |
| **S2** (e.g. backend) | `<repo>-api` | `src/api/**` | integration |
| **CR** (reviewer) | `<repo>-cr` | read-only | main |

*(Illustrative. The real registry is `config/streams.yaml`; the ids `SA`/`S1`/`S2`/`CR` are this framework's conventional vocabulary, not required names.)*

**Gitflow rule (conflict-free):** after a PR merges, do **not** `git checkout <base>` (a base can't be checked out in two worktrees, and streams share bases). Instead `git fetch origin` and branch the next feature **from `origin/<base>`**. Governance/spec artifacts live on the shared base under a git-tracked path and are referenced by repo-relative path — **never** `../OtherWorktree/...`.

**CFR discipline (name your tree):** every claim about repo state must name its **tree** — `git ls-files` (committed) vs. working-tree; which branch; which worktree. Governance/inventory facts cite the committed/shared base, never a local checkout. This rule exists because two carefully grounded reports once disagreed on a simple file count: one had read the working tree, the other the committed branch. Both were "correct"; neither named its tree.

### 2.2 Resilience hooks
Three shared shell scripts installed at `~/.claude/hooks/<hook_namespace>/`, keyed off `$CLAUDE_PROJECT_DIR` so each resolves per-worktree. They are version-controlled in the framework's `hooks/` and installed by `scripts/sync-hooks.sh` (a one-way sync; the tracked copy is the source of truth). **These hooks govern STATE, not memory — they are orthogonal to the vendor auto-memory system.**

| Hook | Fires | Action |
|---|---|---|
| **SessionStart** | start / resume / post-compact | **stdout injected into context** — cats `STATE.md` + git orientation (branch, upstream, uncommitted, last commits) + last journal breadcrumbs + the stream's dispatch inbox. The auto-reload. |
| **Stop** | after each agent turn | Appends `timestamp \| branch@HEAD \| N dirty` to the journal (bounded). No LLM. The recovery trail. |
| **PreCompact** | before compaction | Copies the raw transcript to backups (bounded). The provider does not let a hook *write* a handoff at compaction, so the raw transcript is preserved instead. |

### 2.3 STATE — the "now" spine
- **`STATE.md`** (per-worktree, gitignored) — curated live working state: stream identity/lane, current branch+base, active task, open PRs, next step, gotchas.
- Its `**Stream:** <id>` token is the **dispatch router key** and must be byte-identical to the registry key (§3.4 gate (2)).
- **Proposed evolution:** a small machine-readable `STATE.json` header (§7.4) for drift-checks and provider migration — but **keep raw-file injection**; introduce a renderer only when a tool consumes the header. Do not put a build step in the crash-recovery path before it earns its keep.
- **STATE ≠ memory.** STATE = volatile task-state (L0). Memory = durable knowledge (§8). They compose because their scopes are disjoint; STATE may *reference* a memory by name but never duplicate it.

---

## 3 · L1 — Control plane

### 3.1 Stream registry — `config/streams.yaml`
The single authoritative registry of every stream: lane, base branch, model, role, `governs:` charter pointer, `can_merge`. STATE.md's identity block **derives** from it. **SA reads it to route dispatches and to know who owns what.** Supports ephemeral streams (add + retire in version control). Shape in §7.1.

### 3.2 Ownership map — `ownership.yaml`
Path-glob → owner + escalation rules, so overlap has a defined arbitration path (§7.2). Overlap rules:
- **single-owner path:** other streams *propose*, owner merges;
- **shared path:** proposal PR required;
- **registry/spec files:** SA only.

**Intended to be enforced**, not just declared: a CI/label check that flags a PR touching paths outside the author-stream's ownership. An unenforced map drifts like any doc — and today it *is* unenforced (§10). We prefer ownership + proposal-PR + CI enforcement over hard cross-session file **locking**, which is heavy/fragile at this scale — reserve locking for a proven, recurring conflict.

### 3.3 Dispatch — shared append-only queue (SA is control plane, not mail carrier)
**SA has visibility over all interactions, but is NOT the mandatory relay** (that would make SA a bottleneck + SPOF — an asleep SA would block delivery). Instead:

```
stream → .workflow-runtime/dispatch/  (append-only, addressed envelopes)
              │                              ↑
              │                              └── SA reads the same queue: routing policy, operator log, escalation
              ▼
   receiving stream pulls envelopes addressed to it on SessionStart / loop boundary
```

Envelope schema §7.3. The queue is the **data plane** (transport); SA owns **routing policy + the log** (visibility is structural, not by convention). Envelopes are immutable files; acks are separate per-stream marker files, so a broadcast is consumed independently by each addressee and nothing is ever mutated or deleted — the log is an audit trail.

**Honest limit:** an idle session won't wake itself — acting without the operator only works while a session is active or looping. Sweet spot = queue + SessionStart auto-read + operator-nudge for urgency.

**Live listener — `dispatch watch --stream X`:** the SessionStart auto-read only fires at the session boundary, so an *already-running* session wouldn't see a mid-session arrival until its next boundary. `watch` closes that gap: a long-poll that emits one line per **new** envelope (a Monitor turns each into a notification). It is **per-stream on/off by construction**: launch it for the stream you want watched, stop it to turn it off. It baselines the standing inbox at start (never re-fires the backlog the SessionStart hook already showed) and, on a poll error, prints + keeps polling (never silently dies — *gate-soundness*). It does **not** overcome the honest limit above: an *idle* session still can't be woken.

### 3.4 Disaster recovery — command-first, prompt-second
A prompt-only bootstrap is too lossy to be the primary recovery object. Two parts:
- **`wf doctor`** — a deterministic script emits a structured **recovery report** (§7.5): worktrees + checked-out branches, branch-vs-origin drift, pending envelopes, last STATE headers per stream, latest journal entries, open PRs, uncommitted changes, stale loop leases.
- **SA bootstrap prompt** — reasons over that report: verify infra, reconcile each stream's STATE vs git, regenerate the other streams' restore prompts. See `DISASTER-RECOVERY.md`.
- **`wf doctor --compliance`** — an **operator-machine pre-operationalize gate** (local, offline, read-only), distinct from the recovery report. It must run **where the stream worktrees live** (SA's machine), *not* on a bare CI checkout. For **every** stream in the registry it asserts the stream is present + ready and **exits non-zero** on any shortfall:
  - **(0)** its worktree is **present + unambiguous** — a registry stream with no worktree is itself a FAIL. You cannot operationalize an absent stream, and silently skipping it would let the gate green-light a machine that has *none* of the streams (*gate-soundness*).
  - **(1)** `STATE.md` present — no STATE, no identity, no auto-restore.
  - **(2)** the STATE `**Stream:**` id equals the registry key — parsed with the *exact* `inbox-peek.py` regex, because that token is the dispatch ROUTER key and a mismatch silently misroutes every envelope to the void.
  - **(3)** the live `.claude/settings.json` equals `gen-config` output (merge policy not drifted) — using `gen-config --dry-run` itself as the oracle, so no settings logic is duplicated here to drift.

  It shares doctor's one collision-safe `resolve_streams()` resolver with the report, so gate and report cannot disagree.

*Prompt as UX, script as substrate.*

### 3.5 Loop contracts
Looping is safe **only** with a hard exit contract. Implemented as `loop-template.md` (the contract) + `scripts/loop.py` (`wf loop <start|tick|status|release>` — the deterministic engine that owns the lease + exit-check + guardrails, so the agent never grades its own exit).
- **INPUT:** task + explicit acceptance criteria.
- **EXIT (machine-checkable):** a command returning 0/1. If the exit can't be a command returning 0/1, don't loop it.
- **BUDGET:** max iterations + cost cap.
- **CHECKPOINT:** commit + journal each iteration; **the loop produces a PR, never merges** (the human/review gate stays).

**Four additional guardrails (required, not optional):**
1. **Independent oracle** — the loop must not define *and* grade its own exit in the same lane; at least one check comes from outside the edited lane (prevents reward-hacking).
2. **Max unchanged iterations** — flat diff or the same failing check N times → auto-stop.
3. **Lease + heartbeat** — a lease file (owner, started-at, last-heartbeat, budget) for deterministic crash recovery + stale-loop cleanup. One live loop per stream; `doctor` surfaces stale leases.
4. **Scope-expansion brake** — changes to more than X files outside declared scope → stop and ask the operator.

An **unavailable oracle fails closed** (`tick` exit 23): a timed-out or missing `exit_cmd` is not a "not done yet" verdict, and must never read as "keep looping."

Best fits: fix-until-green tasks, probe loops. Worst fit: open-ended design.

### 3.6 Code-review learning loop (first-class axis)
**Problem:** an internal `/code-review` is structurally **blind** — a reviewer in the same lane and model as the author shares its blind spots; an *external* reviewer is the independent oracle that catches the real defects. And streams **don't learn**: the same mistakes recur.

**Design:**
- **External review stays primary** for correctness/bugs; internal review **narrows to governance/methodology** — what an outside reviewer cannot know.
- **Findings ledger** in git (Tier A), every finding categorized. This repo ships `review-ledger.template.md`; `init.sh` instantiates it as your `review-ledger.md`.
- **Pre-push checklist** — the ledger's top section; the mechanizable classes run as a gate: **`wf pre-push`** (read-only, advisory) greps the branch diff for them and prints the human-eye reminders for the rest.
- **Promotion ladder** (the thresholds that decide when prose becomes a gate):

| Occurrence | Action |
|---|---|
| single | ledger only |
| same category **2× in one lane**, OR once at **P1/P0** | checklist + named **rule** |
| **3 recurrences**, OR any deterministic drift with a cheap mechanical check | **gate** (lint / CI / schema-text regression) |

**rule** = guidance/doctrine; **gate** = mechanized blocker the workflow must satisfy. The difference between "guidance the model forgets" and "a gate it can't bypass."

### 3.7 Config generator & attribution
- **Config generator** — `scripts/gen-config.py` regenerates each registered worktree's `.claude/settings.json` from a **shared floor** (`config/settings-base.json`: allow list, safety deny, hook wiring with a `{{HOOK_NAMESPACE}}` placeholder, plugins), a **project overlay** (`config/project.yaml`: hook namespace, protected paths, extra denies), and the per-stream **`can_merge`** policy from `streams.yaml` — denying `gh pr merge` **and** the GitHub MCP merge tool for non-SA streams. Both surfaces matter: denying only one leaves the gap open. Idempotent; `--dry-run` previews; leaves `settings.local.json` untouched. It deliberately does **NOT** write `model` (a runtime `/model` concern).
- **Attribution** — enable `extensions.worktreeConfig` + per-worktree `git config --worktree user.name`; add a `Stream: <id>` commit trailer; sign-off convention `— [<stream>/<role>]` on PR/issue/review comments; optional labels `stream:*`.
- **Secrets / capability scoping** — a shared MCP config is a capability-leakage risk. Per-stream capability manifests + a SessionStart drift check that reports unexpected tools/servers.

### 3.8 Charters — apply-authority (governance) map — `charters/<stream>.md`
The **dual of the ownership map (§3.2)**. Ownership answers *what a stream may **edit*** (write-authority); a **charter** answers *what rules a stream must **apply*** (apply-authority) — the authoritative domain artifacts governing the *correctness* of its output. Registry field: `governs: charters/<stream>.md`.

Why it's a distinct axis: coordination identity (lane/dispatch/merge) is not knowledge identity — *"what body of rules governs my work."* Without this layer, governance arms **unevenly** (the stream whose work is most dangerous grows a rich governance block because the work forced it; the others don't, so a restart re-arms the file lane but not the rulebook) and **downstream only** (checked at review time — which is exactly the reviewer's lens — but never at each stream's own identity). Catching a violation in review is more expensive than the stream self-applying its rules at wake-time. The charter arms governance **upstream + uniformly**: every stream re-reads its rulebook at SessionStart and self-applies.

- **Content discipline:** each charter line cites a **tracked** anchor (a doc path, a `file:line`, or the originating PR) — never a per-worktree memory file (not shared). It states *when* the rule binds.
- **Base-scoped anchors:** a charter's anchors resolve on the base its stream runs from. A copy present on another base is a *reference copy*.
- **Surfacing:** each STATE.md carries a terse `## Governance` summary + a pointer to its full charter. The charter is the SOT; STATE summarizes to avoid drift.
- **Onboarding:** UC-01 mints a charter for every new stream — a stream isn't onboarded until it has one.

See `charters/README.md`.

---

## 4 · Active listeners (event reaction)

Two tiers. **Nothing pushes mid-turn; every mechanism is pull-at-next-boundary.**
- **Tier 1 — active-while-alive (available today):** a `Monitor` polling `gh api`, a PR-babysitting skill, `dispatch watch`, `/loop`. Capitalize: each stream runs a persistent monitor on its own PRs → polls review + CI, auto-addresses within loop-contract guardrails, notifies on merge-ready / human-decision.
- **Tier 2 — event-driven across sessions (build only on measured pain):** a repository event waking a *dead* session is not available out of the box. When (and only when) missed events from dormant sessions become a measured cost, build a **CI → webhook → dispatch-queue** bridge. Even then, **never "wake agent directly"** — publish to the queue (§3.3), consume at the next active boundary.

---

## 5 · L3 — Provider adapters

Abstract (into `adapters/<provider>/`) the vendor-specific surface: session-launch commands, hook wiring, transcript-backup format, memory-seeding interface, model-registry surface, tool/connector allowlists. **Do NOT** abstract (yet): agent cognition patterns, model-routing logic, a provider-neutral supervisor API. Ports-and-adapters yes; common agent-runtime no.

---

## 6 · L2 — Process model (explicitly out of scope)

The control plane is deliberately agnostic to *what stages work moves through*. A host project brings its own model (tickets, pipeline stages, boards) and binds it in by routing units of work to the scope-appropriate stream. The only contract this framework asserts at L2 is: **a stream is a persistent worktree-bound execution context** — it replaces the "one session = the implementer" model that single-session process docs assume. If your process doc still assumes one implementer session, it is describing a different execution model than the one you are running.

---

## 7 · Schemas

### 7.1 `config/streams.yaml`
```yaml
streams:
  SA: { worktree: myproject,     lane: ["scripts/**"],       base: main,        model: <model-id>, role: orchestrator, governs: charters/SA.md, can_merge: true }
  S1: { worktree: myproject-fe,  lane: ["src/frontend/**"],  base: main,        model: <model-id>, role: frontend,     governs: charters/S1.md, can_merge: false }
  S2: { worktree: myproject-api, lane: ["src/api/**"],       base: integration, model: <model-id>, role: backend,      governs: charters/S2.md, can_merge: false }
```

### 7.2 `ownership.yaml`
```yaml
owners:
  "src/frontend/**": S1
  "src/api/**":      S2
  "scripts/**":      SA
  "docs/**":         shared
escalation:
  single_owner: "propose; owner merges"
  shared:       "proposal PR required"
  registry:     "SA only"
```

### 7.3 dispatch envelope
```yaml
id: <timestamp-uuid>   # append-only, immutable once written
from: S2
to: SA                 # a stream id, or "all" for a broadcast
type: review_request | question | handoff | self_check | <project-defined>
topic: "PR #42 ready for merge"
refs: [PR#42, session:49b8cf49]
priority: P1
created_at: <iso8601>
lease: null            # set by consumer
ack: null              # per-stream ack markers live beside the queue
```

### 7.4 STATE.json header (design)
```yaml
stream: S2
lane: ["src/api/**"]
branch: feature/api-rate-limit
base: integration
active: ["#204"]
open_prs: [204]
last_action: "..."
next_action: "..."
last_dispatch_read: <id>
last_checkpoint: <id>
```

### 7.5 recovery report (emitted by `wf doctor`)
Worktrees + branches · branch-vs-origin drift · pending envelopes · last STATE headers per stream · latest journal entries · open PRs · uncommitted changes · stale loop leases.

---

## 8 · Memory model (three tiers)

> **The gotcha that governs this whole section — vendor memory is base-project-SHARED, not per-worktree.**
> Every git worktree of a repo reads **and** writes the SAME **MAIN** bucket
> (`~/.claude/projects/<main-worktree-abs-path-with-slashes-as-dashes>/memory/` — the slug is machine-specific;
> derive it, never hardcode it). The look-alike per-worktree buckets exist on disk but are **never loaded —
> dead weight, GC candidates.** This was established empirically (a real restart in a non-main worktree
> loaded MAIN's index; a write-probe from that worktree landed in MAIN), correcting an earlier assumption
> that memory was per-worktree and drifting. **Only `STATE.md` is per-worktree.**

Two keying mechanisms, and confusing them is the whole trap:

| Layer | Keyed on | Scope |
|---|---|---|
| `STATE.md` (the SessionStart hook) | `$CLAUDE_PROJECT_DIR` = the worktree | **per-worktree** ✓ |
| vendor auto-memory (`MEMORY.md` + notes) | the base project (main worktree) | **shared by every worktree** |

**Consequences for an adopter:**
- Do **not** migrate memories into a per-worktree bucket to "arm" a stream restart — those files are inert.
- A fresh adopter's bucket is **empty**: it is keyed by *your* repo path, so a new SA starts memory-blind, with none of the accumulated operating lessons. Seed it from git — this repo ships a portable starter set in `memory/` plus an index scaffold `MEMORY.template.md`; `./init.sh --memory` copies them in. **Git is the durable source of truth; the bucket is a thin cache.**

Route by tier:

| Tier | Store | Holds | Rule |
|---|---|---|---|
| **A** | Git (the framework dir, `docs/`, charters) | shared, durable, authoritative — anything another stream must *follow* | needs-to-be-shared → here |
| **B** | vendor auto-memory — the ONE base-project (MAIN) bucket, shared by every worktree (read+write) | common scratch/notes, not authoritative | only-locally-needed → here; keep the index under the load cap |
| **C** | `STATE.md` (per-worktree) | volatile "now" (task/PRs/next step) | doing-right-now → here |

**Index hygiene (Tier B):** `MEMORY.md` is loaded every session under a load cap (~24 KB); **over-cap truncates silently** — recall is lost with no error. Keep it a thin index (one short line per entry), detail in topic files, cold entries in an `ARCHIVE.md` tier.

**Hygiene check — `wf mem-hygiene` (READ-ONLY):** (1) audits the **ONE MAIN bucket** — cap%, ORPHANS (file with no index pointer), DANGLERS (pointer with no file), ARCHIVE cold-tier present; (2) **STATE-REF integrity** — for **each** worktree's `STATE.md`, checks that the memories it names exist in the MAIN bucket (STATE is per-worktree, memory is shared, so a STATE can name a memory MAIN lacks → the "can't recall on restart" gap); (3) lists the **DEAD per-worktree buckets** (GC candidates); (4) proposes a routing target for orphans. **DETECTS + proposes only** — any move or GC is a separate reviewed step.

---

## 9 · Locked decisions

1. **Control plane, not "SDLC framework"** — L0–L3 layering is the spine; L2 belongs to the host.
2. **SA keeps the main root**; every other stream gets a dedicated worktree. Merge capability is scoped SA-only, on both the Bash and MCP surfaces.
3. **Scope-primary streams** — split by file lane, not by base branch. Re-split a stream when its lane grows two independent backlogs, conflicts inside it exceed a threshold, or its review cadence diverges.
4. **The registry is load-bearing** — per-worktree settings are *generated* from `streams.yaml`, never hand-kept.
5. **Review:** external reviewer primary for bugs; internal review = governance-only; learning loop with the §3.6 promotion thresholds.
6. **Active listeners:** Tier-1 now; Tier-2 bridge only on measured pain — publish-to-queue, never wake-agent-directly.
7. **Memory:** three-tier; git = authority; vendor memory = thin shared cache; STATE = now.
8. **Layout-agnostic core** (§1.3) — flat and vendored installs are both first-class, proven by `wf smoke`.

---

## 10 · Status — what exists vs. proposed

Status is split by **where** a thing lives, because L0 is largely operator-environment state that a reader of *this repo* cannot audit (the "name your tree" discipline, §2.1). Do not conflate the two.

**Implemented — in this repo (shared, auditable on any checkout):**
- `scripts/doctor.py` — recovery report **+ `--compliance`** pre-operationalize gate (§3.4, read-only).
- `scripts/dispatch.py` — the append-only cross-stream bus (`send`/`inbox`/`watch`/`ack`/`log`/`show`); immutable envelopes + per-stream ack markers in the canonical main-root `.workflow-runtime/dispatch/`, self-resolved via git-common-dir.
- `scripts/gen-config.py` — registry + settings floor + project overlay → each worktree's `.claude/settings.json`, enforcing `can_merge` on **both** the Bash and GitHub-MCP surfaces.
- `scripts/loop.py` + `loop-template.md` — the loop-contract engine (§3.5): lease + exit-check + budget/max-unchanged/scope-brake guardrails; oracle-unavailable fails closed. Produces a PR, never merges.
- `scripts/mem-hygiene.py` — the §8 memory-bucket detector (read-only).
- `scripts/pre-push-check.py` — `wf pre-push`, the advisory recurring-class diff guard (§3.6).
- `scripts/decoupling-lint.py` — the zoned host-noun gate that keeps the core generic; fails loudly when it has no config to enforce.
- `scripts/smoke-fresh-repo.sh` — the behavioral genericity gate: a blank repo stands up the substrate **in both layouts** (§1.3).
- `scripts/wf` — the branch-independent, layout-agnostic launcher; `scripts/sync-hooks.sh` — the one-way hook installer; `scripts/_cp_paths.py` — the single layout resolver.
- `hooks/` — the three resilience hooks + `inbox-peek.py` (the tracked source of truth for what `sync-hooks` installs).
- Tracked docs + templates: this spec, `README.md`, `QUICKSTART.md`, `DISASTER-RECOVERY.md`, `SA-BOOTSTRAP.md`, `charters/` (README + `_TEMPLATE.md` + a generic `SA.md`), `use-cases/UC-00..04`, `review-ledger.template.md`, `runtime.md`, `loops/`, `config/*.example.yaml`, `config/settings-base.json`, `init.sh`, and the portable memory starter set (`memory/` + `MEMORY.template.md`).

**Implemented — operator environment (per machine, NOT repo-auditable):** the worktrees themselves; the hooks installed under `~/.claude/hooks/<hook_namespace>/`; per-worktree `STATE.md` (gitignored), journals + transcript backups; per-worktree `.claude/settings.json` (generated); the vendor memory bucket; and **this repo's own overlay** (`config/project.yaml`, `config/streams.yaml`, `ownership.yaml`, `review-ledger.md` — untracked here by design; see the README). These are real on the machine that has them but **by definition unverifiable from any other checkout**. To corroborate this paragraph where the worktrees live, run `wf doctor`. A reader elsewhere still cannot verify it — they would get *their* machine's topology.

**NOT implemented anywhere (DESIGN only):** ownership CI enforcement (§3.2 — `ownership.yaml` is data + convention, consumed by no tool); `governs:` pointer-resolution checking (charters are consumed by convention, like ownership); the `STATE.json` header (§7.4); per-worktree git attribution (`worktreeConfig` + `Stream:` trailers, §3.7); capability manifests / MCP drift check (§3.7); framework-self-CI (the gates exist as commands, but nothing runs them automatically); the remaining `.workflow-runtime/` contents (snapshots, checkpoints, override log — see `runtime.md`); provider adapters (§5); the Tier-2 event bridge (§4).

This spec must be read as **design**; do not treat any proposed mechanism as live until it appears in an "Implemented" list above — and note *which* list, repo vs operator environment.

---

## 11 · Open questions (carry forward)

- **Framework-self-CI** — the gates (`decoupling-lint --zone core`, `smoke`) are commands nobody runs on a schedule. Wiring them to CI is the obvious next mechanization, and needs the overlay question answered first: a CI checkout has no `config/project.yaml` until it runs `init.sh`.
- **Subtree round-trip** — consuming this repo via `git subtree --prefix=` works by construction (§1.3), but the *upgrade* path for a host whose overlay has diverged is unproven.
- Framework-native observability metrics (restore-time, archaeology-count, dispatch latency, stale-state age, loop-abort rate, cross-stream conflict rate) — phase in cheap ones first.
- Runtime GC policy (stale envelopes, dead leases, old journals, abandoned worktrees).
- Human-override semantics — where "stop loop / force route / ignore stale" is recorded for DR + audit.
