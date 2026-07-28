# Stream charters — the governance / apply-authority layer

A **charter** is a stream's *rulebook*: the authoritative domain artifacts that stream must **apply**
to the substance of its work. It is the **dual of `lane`** in the registry:

| Registry field | Question it answers | Kind of authority |
|---|---|---|
| `lane` (`streams.yaml`) | *What files may I **edit**?* | **write**-authority (coordination) |
| `governs:` → `charters/<stream>.md` | *What rules must I **apply**?* | **apply**-authority (governance) |

## Why this layer exists

The control plane models **coordination** well — who owns which files (`lane`), how streams talk
(dispatch), who merges (`can_merge`). But coordination identity is not the same as **knowledge
identity**: *"what body of rules governs the correctness of my output."*

Before this layer, governance was armed **unevenly and downstream**:

- **Uneven** — the stream whose work is most dangerous grows a rich `## Governance` block in its STATE,
  because that work forces the discipline. The other streams never do, so a restarted stream re-arms its
  *file lane* but not its *rulebook*. (The tell: ask a stream its role and it recites lane + procedure,
  saying nothing about the domain canon it is supposed to uphold.)
- **Downstream** — governance was checked at **review time** (that is literally the reviewer's lens)
  but never **armed upstream** at each stream's identity. Catching a violation in review is more
  expensive than the stream self-applying its rules at wake-time.

The charter arms governance **upstream and uniformly**: every stream re-reads its rulebook at
SessionStart, so it self-applies rather than relying on CR to catch drift after the fact.

## How it's wired

1. **`streams.yaml`** carries `governs: charters/<stream>.md` — the tracked pointer (Tier A).
2. **`charters/<stream>.md`** is the rich manifest — enumerates each artifact, *when* it
   binds, and cites a tracked anchor (a doc path, a `file:line`, or the originating PR — never a
   per-worktree memory file, which isn't shared).
3. Each stream's **STATE.md** carries a short `## Governance` surfaced summary + a pointer to its full
   charter (the same way `lane` in yaml surfaces as a terse "do NOT touch X" line in STATE).
4. **Onboarding (UC-01)** mints a charter for every new stream — a stream is not onboarded until it has
   one.

## Discipline for charter content

- **Cite tracked anchors resolvable on the stream's OWN base.** A charter line points to something present
  on the base its stream runs from (`streams.yaml` `base`; each charter states its **Base:**) — a `docs/*`
  path, a `file:line` in the code it depends on, or a PR number for the "why". Anchors are
  **base-scoped**: a charter present on another base (via the the framework dir sync) is a *reference copy* —
  its cross-base anchors resolve on the owning stream's base, not necessarily the local tree — streams that
  fork off different bases will have anchors present on different trees. Do **not** anchor on
  auto-memory (path-scoped, not shared) — memory may *summarize* a rule, but the charter cites its durable
  source.
- **Say when it binds.** "Mandatory before any engine/matrix change" is more useful than a bare link.
- **Apply-authority, not edit-authority.** A charter may bind a stream to artifacts it must *obey* but
  may not *edit* (e.g. a probe stream applies the rules another stream owns; it never edits them).
