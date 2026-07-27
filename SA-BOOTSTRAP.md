# SA bootstrap — run the orchestrator for THIS repo (portable SA startup kit)

This is the **portable SA session startup**: the same way you bring up the orchestrator (SA) role in *any*
repo that adopts this control plane. Extracted/generalized from AsterClaude's SA discipline.

## Launch prompt (paste into a fresh Claude Code session started in this repo's root)

> You are **SA (super-agent / orchestrator)** for the **`ai-workstream-control-plane`** project.
> Your job: coordinate streams, own the control-plane framework, and merge PRs post-review (SA-only).
> On start: read `STATE.md` (your live spine), your charter `charters/SA.md`, `config/streams.yaml`
> (the registry), and `control-plane-spec.md` (the model; §10 = live-vs-design SOT). Your tools are
> `wf <dispatch|doctor|gen-config|mem-hygiene|loop|pre-push|decoupling-lint|smoke|sync-hooks>`.
> Disciplines: **merge only post-review**; every PR body has a review/verification note; **name your tree**
> on any repo-state claim; sign off SA-authored PRs/issues/comments with `— [SA / orchestrator]`.
> **First task: the E2 extraction below.**

(The SessionStart hook — once `sync-hooks` has installed it — will auto-inject `STATE.md` + git orientation
+ the dispatch inbox each session, so this prompt is only needed for the very first bring-up.)

---

## First task — E2 extraction (populate this repo from AsterClaude's `workflow/`)

The generic core is **already decoupled** in AsterClaude (`workflow/`, main @ `5e1377a`): `decoupling-lint
--zone core` is green and `wf smoke` proves a blank repo bootstraps. So extraction is mostly a **curated
copy** of the generic subset + the templates — NOT re-authoring.

### Bring IN (generic core + templates — copy from `AsterClaude/workflow/`)
- `scripts/` — doctor.py, dispatch.py, gen-config.py, loop.py, mem-hygiene.py, pre-push-check.py,
  decoupling-lint.py, smoke-fresh-repo.sh, wf, sync-hooks.sh
- `hooks/` — session-start.sh, stop-journal.sh, pre-compact.sh, inbox-peek.py
- `config/` — settings-base.json, project.example.yaml, streams.example.yaml  (+ an ownership.example.yaml)
- `charters/` — README.md, _TEMPLATE.md, **SA.md as a generic template** (the startup-kit charter)
- `loops/` — README.md; `loop-template.md`; `QUICKSTART.md`; `use-cases/` (UC-00..04, generalized)
- `review-ledger.template.md` (the generic checklist + an EMPTY evidence table)
- `DISASTER-RECOVERY.md` (generalized), this `SA-BOOTSTRAP.md`, an `init.sh`

### Leave BEHIND (AsterClaude overlay — do NOT copy)
- `config/streams.yaml`, `config/project.yaml`, `ownership.yaml`, the concrete `charters/{SA,S1,S2,S3,VLVR,CR}.md`,
  the populated `review-ledger.md`, and AsterClaude nouns in `README.md` / `control-plane-spec.md` (genericize).

### ⚠️ Layout decision to resolve FIRST (blocks a clean extraction)
The scripts assume a `workflow/` path layer: `SCRIPT.parents[2]` = repo root and config at
`<repo>/workflow/config/...`. Two options:
- **(A) Keep a `workflow/` dir in this repo** (`ai-workstream-control-plane/workflow/scripts/…`). Standalone
  use works unchanged; **subtree consumption** then needs AsterClaude to `git subtree pull --prefix=workflow`
  from *this repo's `workflow/` split* (extra `subtree split` step), or accept `workflow/workflow` nesting.
- **(B) Flatten to repo root** (`scripts/` at root) and make the scripts **layout-agnostic** (resolve their
  base via `git rev-parse --show-toplevel` and find `config/` relative to that, not a hardcoded `workflow/`).
  Cleanest subtree (`--prefix=workflow` maps root→workflow/), but requires a small refactor of the
  `parents[2]` / `"workflow"/"config"` assumptions in doctor/gen-config/mem-hygiene/decoupling-lint/loop.
- **Recommendation: (B)** — do the layout-agnostic refactor once; it's the honest fix and makes subtree clean.
  Re-run `wf smoke` after to prove it still bootstraps.

### Verify
- `decoupling-lint --zone core` → 0 · `wf smoke` → green · then commit + push `main`.

### Then E3 / E4
- **E3:** in AsterClaude, replace `workflow/` core with a `git subtree` of this repo (keep the overlay);
  document the `subtree pull` upgrade path.
- **E4:** bootstrap a throwaway repo from this one (`init.sh` → `wf smoke`) — the final fresh-repo proof.
