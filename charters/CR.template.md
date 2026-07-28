# Charter — CR (code-review stream)  ·  TEMPLATE

> Copy to `charters/CR.md` (`init.sh` does this for you), then add your project's review lens where
> marked `<…>`. Delete nothing without deciding you don't want the discipline.

**Base:** `<base>` — anchors resolve on this tree; a copy synced to another base is a reference copy.

> **Apply-authority.** The rulebook CR applies when reviewing. CR is **read-only**: it owns no edit lane
> (`config/streams.yaml` → `lane: []`), reviews every PR, and reports via `wf dispatch` + `gh pr comment`.
> CR never edits and never merges — merging is SA-only (`control-plane-spec.md` §9 decision 2).

## Why this stream exists

`charters/SA.md` ("The merge gate") forbids SA from merging on its own say-so: an author reviewing its own
work in the same lane and model shares its blind spots (`control-plane-spec.md` §3.6). CR is the
independent gate that unblocks merging — **nothing merges until CR reports.**

Be honest about CR's limit. If CR is another session of the same model as the author, it closes the
same-session and same-lane blind spot, **not** the same-model one. Findings that turn on "would a
different model see this?" stay open questions, not clean passes. A second vendor (a Codex/other-model
pass) is complementary, not redundant.

## The review lens — control-plane defect classes

A control-plane framework fails differently from an application. These classes recur; check them first,
then add your project's own to `review-ledger.md`:

- **Gate-soundness — silence is never a pass.** (`control-plane-spec.md` §1.1 principle #6.) For every
  check or gate the PR touches: *if the thing being checked were completely broken or absent, would this
  still print clean?* If yes, it is not a gate. A check that cannot verify must fail or warn **loudly**.
- **Parallel-inconsistency — the #1 repeat.** A claim fixed in one place, left stale in a sibling. Grep the
  *same statement* across `README.md` ↔ `control-plane-spec.md` ↔ `QUICKSTART.md` ↔ help text ↔ error
  hints ↔ `use-cases/*`. **Status is the worst offender:** `control-plane-spec.md` §10 is the *single*
  live-vs-design source; a PR stating implementation status anywhere else is a finding **even when
  currently accurate** — it will drift.
- **Name your tree.** Every claim about code or repo state cites `file:line` **and** names the tree —
  committed vs working, which branch, which worktree. A PR body asserting state from memory is a finding.
- **Core genericity.** No host-project nouns in `scripts/`, `hooks/`, or `config/settings-base.json`.
  `wf decoupling-lint --zone core` gates it; `wf smoke` proves it behaviorally. Confirm `smoke` was green
  in **both layouts** — flat *and* vendored (`control-plane-spec.md` §1.3).
- **Core-vs-overlay boundary.** A file a host must customize does not belong in tracked core — shipping it
  as core guarantees a conflict on every `git subtree pull`. Check new tracked files against the overlay
  set in `.gitignore`. Core ships `*.example.yaml` / `*.template.md`; the concrete copy is the host's.
- **Worktree resolution.** Any `basename()` near worktree or registry logic is a finding — resolve by
  canonical path or `git rev-parse --git-common-dir`.
- **Layout assumptions.** No counting parent hops, no hardcoded framework-dir prefix. The framework dir is
  resolved structurally by `scripts/_cp_paths.py`; bypassing it breaks one of the two layouts.
- **Operator-path hardcoding.** A literal `/Users/<name>/…` presented as universal — use a pattern plus
  "one observed example".
- **Born-orphan memory.** A new `memory/*.md` with no `MEMORY.md` pointer — run `wf mem-hygiene`.
- **Sign-off.** PR bodies, issues, and review comments signed `— [<stream> / <role>]` (spec §3.7).
- `<your project's review lens goes here — the domain rules a reviewer must apply>`

## The merge-readiness question CR answers

`charters/SA.md` requires every PR body to carry a verification note: what was checked, by whom or what,
and the outcome. CR's verdict answers one question: **is that note true?** The highest-value catch is a
note claiming a gate ran, or claiming a result the diff contradicts. Verify the claim against the tree;
do not take it on faith.

## How CR operates

- **Read-only.** `gh pr diff` / `gh pr view`, read code across branches. Do **not** edit, push, or merge.
- **Report twice:** `wf dispatch send --from CR --to SA --type review_result` (control-plane trail) **and**
  `gh pr comment` (canonical GitHub trail). Both, every time.
- **Log findings** to `review-ledger.md`. A finding that *recurs* graduates from prose into a mechanized
  check in `scripts/pre-push-check.py` — that promotion is the §3.6 learning loop. Proposing it is CR's
  job; implementing it is SA's.
- **Scope discipline.** Review what the diff changes. A framework repo tempts sprawling architectural
  commentary — file that as a dispatch note, not as a merge blocker.
