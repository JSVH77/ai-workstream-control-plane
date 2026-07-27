# Charter — <STREAM_ID> (<role>)

> Copy to `charters/<STREAM_ID>.md`, fill in, and point the stream's `governs:` field at it in `streams.yaml`.
> A charter is **apply-authority** (what this stream must OBEY) — the dual of the lane's **edit-authority**
> (what it may change, in `ownership.yaml`). Keep it terse; it's surfaced as a `## Governance` block in the
> stream's STATE.md at onboarding (UC-01).

## Base
- **Base branch:** <main | integration>  — this stream PRs into and forks features from `origin/<base>`.
- Governance/spec artifacts are referenced by repo-relative path on the base, never `../OtherWorktree/...`.

## Apply-authority (the rulebook this stream OBEYS)
- <the authoritative domain artifacts / methodology docs this stream must follow — link by repo-relative path>
- <e.g. coding standards, a design system, a domain spec, review disciplines>

## Merge / gates
- **Merge:** <SA-only, post-review — or this stream's policy>. `can_merge` in `streams.yaml` enforces it.
- **Before push:** run `wf pre-push`; address the project's recurring review classes (see `review-ledger.md`).

## Anchors (cited artifacts — name the tree)
- <file:line or symbol references this stream depends on; keep them on the base where the code lives>

## Notes / gotchas
- <stream-specific footguns worth surfacing at every session start>
