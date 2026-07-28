# UC-05 — Consume (or upgrade) the control plane in a host project via `git subtree`

**Scenario:** a host project already has its own code and wants the control plane vendored under a prefix
(`workflow/`, `tooling/cp/`, anything — the core is layout-agnostic, spec §1.3). Either it has **never**
vendored the core, or it has an **older copy** it now wants upgraded.

**Actors:** **Host SA** (the orchestrator of the consuming repo) · **Framework SA** (the control-plane
repo's orchestrator) · **Operator**.

**Principle:** the host owns its **overlay**; upstream owns the **core**. A pull must never clobber the
host's registry, ledger, ownership map, or **merge gates**. That is why core ships `*.example.yaml` and
`*.template.md` rather than filled-in copies (see the README, "Why the overlay is not tracked here").

---

## Part A — first-time consumption

| # | Actor | Step |
|---|---|---|
| 1 | **Host SA** | **Inventory the divergence first.** If a hand-copied core already exists under the prefix, diff it against upstream *before* touching anything: which files are identical, which diverged, which are host-only. Host-only files are the overlay you must preserve. Never skip this — a silent overwrite of a charter is not recoverable from the diff alone. |
| 2 | **Host SA** | **Name the overlay explicitly.** Minimum set: `config/project.yaml`, `config/streams.yaml`, `ownership.yaml`, `review-ledger.md`, and every concrete `charters/*.md`. Copy them out of the tree to a scratch dir. |
| 3 | **Host SA** | Branch: `git checkout -b chore/vendor-control-plane`. |
| 4 | **Host SA** | `git subtree add` **refuses a prefix that already exists**, so remove the old copy first: `git rm -r <prefix> && git commit`. This is why step 2 is not optional. |
| 5 | **Host SA** | `git subtree add --prefix=<prefix> <framework-remote> <ref> --squash`. Use `--squash` unless you genuinely want the framework's full history interleaved into the host log; `--squash` keeps the host history readable and still supports later pulls. |
| 6 | **Host SA** | **Restore the overlay** from step 2 into the prefix. |
| 6b | **Host SA** | **`git add -f` every overlay file — this step is mandatory and non-obvious.** The core's own `.gitignore` travels with it into `<prefix>/`, and git resolves ignore rules with the **deepest** file winning, so `<prefix>/.gitignore` ignores the host's *own* charters and config. A negation in the host's root `.gitignore` does **not** rescue them. Without `-f` the overlay is silently absent from every fresh clone: <br>`git add -f <prefix>/charters/*.md <prefix>/config/project.yaml <prefix>/config/streams.yaml <prefix>/ownership.yaml <prefix>/review-ledger.md` <br>Once tracked, ignore rules no longer apply to those paths — later edits and pulls behave normally. Then commit. |
| 7 | **Host SA** | Run `<prefix>/init.sh` if any overlay file is missing — it renders what's absent from the templates and is non-destructive to what exists (`[keep]` for every file already present). Anything it creates also needs step 6b. |
| 8 | **Host SA** | `bash <prefix>/scripts/sync-hooks.sh` then `python3 <prefix>/scripts/gen-config.py`. **Restart the session** — settings are read at session start. |
| 9 | **Host SA** | **Prove it:** `wf doctor --compliance` (every registry stream present + compliant) · `wf decoupling-lint --zone core` (0 hits) · `wf smoke` (green in both layouts). |
| 10 | **Host SA** | Open the PR. Body carries the verification note: what ran, and the outcome. Host CR reviews; host SA merges. |

## Part B — upgrading a host whose overlay has diverged

| # | Actor | Step |
|---|---|---|
| 1 | **Host SA** | `git subtree pull --prefix=<prefix> <framework-remote> <ref> --squash` on a branch, never on the base. |
| 2 | **Host SA** | **Expect conflicts only in the shared narrative** — `README.md`, `control-plane-spec.md`, `QUICKSTART.md`, `DISASTER-RECOVERY.md`. Overlay files should not conflict: they exist in *ours*, never in the subtree history, so the three-way merge leaves them alone. **If an overlay file conflicts, stop** — it means that file is being tracked upstream too, which is a boundary bug worth reporting to Framework SA rather than resolving locally. |
| 3 | **Host SA** | Resolve narrative conflicts in favour of upstream **unless** the host deliberately customized the file. A host that keeps editing shared narrative in place will conflict on every pull — the durable fix is to keep host-specific prose in host-owned docs and leave the vendored narrative pristine. |
| 4 | **Host SA** | Re-run steps **7–9** of Part A (init.sh, hooks, gen-config, restart, the three gates). A pull can add a script whose hook wiring or settings floor changed — and it can ship a **new overlay template**, whose rendered file needs step 6b's `git add -f` or it stays silently untracked. Skipping step 7 here reproduces Part A's failure mode on the upgrade path. |

## Verification checklist

- [ ] **`git ls-files <prefix>/charters/` is non-empty and lists the concrete `<stream>.md` files** (not
      just `*.template.md`). Same for `git ls-files <prefix>/config/streams.yaml`. *Presence on disk is
      not evidence* — an ignored file is present, looks correct, and vanishes on the next clone. Check
      **tracking**, not existence.
- [ ] Every overlay file from Part A step 2 is present and **unchanged** after the add/pull.
- [ ] `wf doctor --compliance` passes for every registered stream.
- [ ] `wf decoupling-lint --zone core` = 0 hits.
- [ ] `wf smoke` green in **both** layouts.
- [ ] The host's `charters/SA.md` still carries the host's merge gates (not the generic template's).
- [ ] `git log --oneline <prefix>` shows the subtree commit — the upgrade path is reproducible.

## Notes / gotchas

- **`--squash` consistency.** If you added with `--squash`, pull with `--squash`. Mixing the two produces
  a confusing history and can resurrect files you deliberately dropped.
- **Stale long-lived branches are the real hazard.** A host branch that forked *before* the vendoring, and
  carries its own copy of the core under the same prefix, will try to resurrect the old core when it
  merges. Inventory those branches **before** the subtree lands (`git log --oneline main..<branch> --
  <prefix>`), and rebase or re-cut them after. This bites long after the PR merges, which is what makes it
  dangerous.
- **The prefix is free.** Nothing counts parent hops; `scripts/_cp_paths.py` resolves the framework dir
  structurally. Vendoring under `tooling/cp/` works exactly as well as `workflow/`.
- **Host-side `wf`.** `sync-hooks.sh` installs `wf` into `~/.claude/hooks/<hook_namespace>/`; the namespace
  comes from the host's `config/project.yaml`. Two projects on one machine need **different** namespaces or
  they overwrite each other's hooks.
