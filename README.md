# AI Workstream Control Plane

**A reusable control plane for running several long-lived Claude Code sessions (streams) in parallel on one
repository — without losing state to crashes, colliding on files, or drifting apart.**

This is the **project-agnostic** framework. A host project adds only its overlay (`config/project.yaml`,
`config/streams.yaml`, `ownership.yaml`, `review-ledger.md`, `charters/*.md`).

> **New here?** → [`QUICKSTART.md`](QUICKSTART.md) (day-0 stand-up, ~10 min) ·
> [`use-cases/UC-00-bootstrap-fresh-repo.md`](use-cases/UC-00-bootstrap-fresh-repo.md) (the playbook) ·
> [`control-plane-spec.md`](control-plane-spec.md) (the model — **§10 is the live-vs-design source of truth**).

## Who this is for

You want to run several Claude Code sessions on the *same repository at once* — say a frontend session, a
backend session, and an orchestrator coordinating them. This repo is what makes that setup **survivable and
coordinated** instead of chaotic.

If you're running a single session, you don't need any of this. The value starts at **two or more
long-lived sessions** on one codebase.

## The problem it solves

Run parallel sessions on one repo and seven things break:

| The break | The fix |
|---|---|
| a crash or compaction wipes a session's in-context state | **resilience hooks** — save state continuously, re-inject it on restart |
| sessions collide on the same files | **one git worktree per stream**, each scoped to a file **lane** |
| no way to hand work between sessions | a **shared append-only dispatch bus** + SA as observer/orchestrator |
| each session's config drifts | a **registry** + **config generator** — every session's settings from one source |
| memory fragments | **three-tier memory** — durable knowledge in git, not scattered per-session |
| git turns chaotic | **gitflow rules** + a **`doctor`** tool and a DR runbook to see and recover the whole setup |
| the same review findings recur | a **review learning loop** — ledger → `wf pre-push` guard → `doctor --compliance` gate |

## The model in one picture

```
          ┌──────────────────────────────────────────────────────────┐
          │  git repo (one project)                                   │
          │                                                           │
   SA ────┤  myproject        (main root, orchestrator)               │
   S1 ────┤  myproject-fe     (frontend lane)          worktrees      │
   S2 ────┤  myproject-api    (backend lane)                          │
   CR ────┤  myproject-cr     (review lane, read-only)                │
          └──────────────────────────────────────────────────────────┘
   each session = one stream = one worktree, scoped to a lane
   coordination = a shared append-only dispatch queue (direct --from/--to; SA observes, is not a relay)
   durable knowledge = git (Tier A) · vendor memory = shared thin cache (Tier B) · STATE.md = "now" (Tier C)
```

- **Stream** = one long-lived session, bound to one **git worktree**, responsible for one file **lane**.
  Streams are separated by *scope*, not by branch.
- **SA** (super-agent) = the orchestrator session. It sees everything, routes work, and is the only stream
  that merges PRs (post-review).
- The **registry** (`config/streams.yaml`) is the single source of truth for who's who.

## The seven pieces (and where they live)

1. **Resilience** — three hooks (`hooks/`): `SessionStart` re-injects each stream's `STATE.md` + git
   orientation + its dispatch inbox; `Stop` appends a recovery breadcrumb; `PreCompact` backs up the
   transcript. Installed to `~/.claude/hooks/<hook_namespace>/` by `scripts/sync-hooks.sh`.
2. **Isolation & governance** — worktree-per-stream + `ownership.yaml` (path-glob → owner: *what you may
   **edit***) + `charters/<stream>.md` (each stream's rulebook: *what you must **apply***, pointed at by
   `governs:` in the registry), so streams stay in lane **and** on-method.
3. **Coordination** — `scripts/dispatch.py`, an append-only cross-stream bus
   (`send`/`inbox`/`watch`/`ack`/`log`/`show`; `watch` is a live listener for an already-running session).
4. **Consistency** — `config/streams.yaml` + `scripts/gen-config.py`, which regenerates each worktree's
   `.claude/settings.json` from one shared floor + per-stream policy (e.g. SA-only merge).
5. **Recovery** — `scripts/doctor.py` (read-only health/topology report) + [`DISASTER-RECOVERY.md`](DISASTER-RECOVERY.md).
6. **Deterministic gates** — `review-ledger.template.md` logs every review finding; recurring classes
   graduate into `wf pre-push` (advisory diff-grep) and `wf doctor --compliance` (a pre-operationalize gate).
7. **Safe autonomous loops** — `loop-template.md` + `scripts/loop.py` (`wf loop`). A stream can iterate
   fix-until-green *only* behind a deterministic engine that owns the exit-check + guardrails (budget ·
   max-unchanged · scope-brake · lease/heartbeat). **The loop opens a PR; it never merges.**

`scripts/wf` is a thin launcher so any stream runs the tools from any branch:
`wf dispatch|doctor|gen-config|mem-hygiene|loop|pre-push|decoupling-lint|smoke|sync-hooks`.

## Install

Two supported layouts — **neither is assumed anywhere in the code** (spec §1.3):

**A · Standalone / flat** — clone this repo and work in it, or copy its contents into your repo root.
```bash
./init.sh              # generate your overlay from the *.example.yaml templates
./init.sh --memory     # ...and seed the vendor memory bucket (recommended — see "Memory", below)
```

**B · Vendored into an existing repo** — any prefix you like:
```bash
git subtree add --prefix=workflow <this-repo-url> main --squash
bash workflow/init.sh
```

Then follow the steps `init.sh` prints (edit the overlay → mint charters → add worktrees →
`sync-hooks` → `gen-config`) and prove it with the two gates:

```bash
wf doctor --compliance    # every registered stream present · STATE-id == registry · settings == gen-config
wf smoke                  # a blank repo stands up the whole substrate, in BOTH layouts
```

Your repo needs these `.gitignore` entries (`init.sh` does not write them for you):
`.workflow-runtime/`, `__pycache__/`, `STATE.md`, `STATE.journal.md`, `.claude/settings.local.json`.

> **Restart the session after `init.sh`.** Settings load at session *start*, so the session that bootstraps
> the repo is still running on your global permissions — no project floor. This repo ships a **committed
> baseline** `.claude/settings.json` so a fresh clone has the safety denies immediately, and `gen-config`
> specializes it per worktree; but only a restart makes either live in your session. Personal overrides go
> in `.claude/settings.local.json`, which `gen-config` never touches. (Spec §3.7.)

## Everyday commands

```bash
wf doctor                              # topology + health across all streams
wf doctor --compliance                 # the readiness gate (exits non-zero on any shortfall)
wf dispatch send --from S1 --to SA --type review_request --topic "PR #42 ready" --refs PR#42
wf dispatch inbox --stream SA          # auto-shown at SessionStart; `watch` for a live listener
wf loop start --contract loops/<name>.md   # safe fix-until-green loops (see loop-template.md)
wf pre-push                            # advisory guard for recurring review classes before you push
wf mem-hygiene --routing               # memory bucket audit (read-only)
```

## Memory — the one thing that surprises everyone

The vendor auto-memory bucket is **shared by every worktree of a repo**, not per-worktree: they all read
*and* write the same MAIN bucket, keyed on the main worktree's path. The look-alike per-worktree buckets
exist on disk but are **never loaded** — dead weight. **Only `STATE.md` is per-worktree.**

Two consequences: don't seed a per-worktree bucket to "arm" a stream (inert), and — because the bucket is
keyed on *your* repo path — **a fresh adopter starts memory-blind**. This repo ships a portable starter set
of operating disciplines in [`memory/`](memory/) plus an index scaffold (`MEMORY.template.md`);
`./init.sh --memory` copies them into your bucket. Git is the durable source of truth; the bucket is a
thin cache. Full model: spec [§8](control-plane-spec.md).

## Why the overlay is not tracked here

This repo tracks the framework **core** plus its `*.example.yaml` / `*.template.md` templates. The concrete
overlay — `config/project.yaml`, `config/streams.yaml`, `ownership.yaml`, `review-ledger.md`, and the
concrete `charters/*.md` — is **gitignored here** and generated by `init.sh`.

That is deliberate: this repo is meant to be *consumed* (vendored via subtree), and an upstream pull must
never clobber a host's own registry, ledger, or merge gates. **Charters are in that set for a concrete
reason:** a host's `charters/SA.md` carries *its* merge gates and domain rules — shipping a filled-in
`SA.md` as core would overwrite them on subtree-add and conflict on every pull thereafter. Core ships
`SA.template.md` / `CR.template.md`; the concrete copy is the host's. In a **host** project those same
files *are* tracked (Tier A) — that is where they belong.

> ⚠ **Vendored hosts: tracking the overlay takes one extra step.** This repo's `.gitignore` travels into
> your `<prefix>/` on a subtree add, and git resolves ignore rules with the **deepest** file winning — so
> it ignores *your* charters and config, and a negation in your root `.gitignore` will not override it.
> Run `git add -f` once per overlay file (see [`use-cases/UC-05`](use-cases/UC-05-consume-via-subtree.md)
> step 6b); after that they are tracked normally. Skip it and your overlay is missing from every fresh
> clone, while looking perfectly fine on the machine that created it.

The trade: a fresh clone of *this* repo can't run `decoupling-lint` or `gen-config` until `init.sh` has
run, since both need an overlay to read. That is also why framework-self-CI is still an open question
(spec §11).

## Folder map

```
scripts/            wf · doctor · dispatch · gen-config · loop · mem-hygiene · pre-push-check
                    decoupling-lint · smoke-fresh-repo · sync-hooks · _cp_paths (the layout resolver)
hooks/              session-start · stop-journal · pre-compact · inbox-peek  (synced to ~/.claude/hooks/)
config/             settings-base.json (the shared floor) + project/streams/ownership *.example.yaml
charters/           README · _TEMPLATE.md · SA/CR *.template.md  (apply-authority; `governs:` points here)
loops/              loop contracts (tracked); the live lease is gitignored runtime
use-cases/          UC-00 bootstrap · UC-01 onboard · UC-02 recover SA · UC-03 restart · UC-04 dry-run
                    UC-05 consume/upgrade via git subtree
memory/             portable discipline memories to seed a fresh adopter's (empty) vendor bucket
control-plane-spec.md   the model + §10 live-vs-design status (the contract)
QUICKSTART.md · DISASTER-RECOVERY.md · SA-BOOTSTRAP.md · loop-template.md · runtime.md
review-ledger.template.md   the review learning loop (init.sh → review-ledger.md)
init.sh             day-0 overlay bootstrap (idempotent, non-destructive)
.workflow-runtime/  gitignored live state (dispatch queue, leases) — never committed
```

## What's live vs. still design

**See the spec's [§10](control-plane-spec.md)** — the single maintained status list (repo-auditable /
operator-environment / design-only). No status list is kept here on purpose: a duplicated one drifts.
