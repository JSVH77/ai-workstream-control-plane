---
name: name-your-tree-cfr
description: "Every claim about code or repo state must name the TREE it came from — committed vs working, which branch, which worktree. Two grounded reports disagreed on a file count because one read the working tree and the other the committed branch; both were 'right'."
metadata:
  node_type: memory
  type: feedback
---

**The rule:** any assertion about what the repository contains — a file count, "X already exists", "that
function is gone", "the config says Y" — must state **which tree** it was read from:

- **committed** (`git ls-files`, `git show <ref>:<path>`) vs **working tree** (what's on disk right now),
- **which branch / base** (a feature branch, `main`, an integration branch),
- **which worktree** (in a multi-worktree setup, "the repo" is ambiguous — several checkouts exist).

**Why (the incident):** two carefully grounded inventory reports disagreed — 104 items vs 97 — on the same
question. Neither was lying: one had counted the local working tree (with uncommitted additions), the other
the committed shared base. Both were "correct" and the disagreement was unresolvable until someone asked
which tree each had read. Hours went into reconciling a difference that naming the tree would have
prevented in one line.

**The failure mode this belongs to — "memo-as-truth":** asserting repo state from memory or from an
earlier turn's summary, rather than re-reading it. Memory is a *cache of a tree at a time*; the tree moves.
Governance and inventory facts must cite the **committed, shared** base — never a local checkout — because
a local checkout is unverifiable by anyone else.

**How to apply:**
1. Before any "what exists" claim: `git fetch`, then read the specific tree you intend to cite.
2. Cite `file:line` **and** the tree. Prefer *symbol* anchors to line numbers for cross-base references —
   line numbers rot across rebases.
3. In a PR or review comment, if the claim is about the shared base, say so explicitly: a reviewer's
   checkout is a different tree, and a claim they can't reproduce reads as a wrong claim.
4. If you cannot verify which tree, say the claim is unverified. An honest gap beats a confident mismatch.

Related: [[gate-soundness]] (same shape — a claim that *couldn't* be checked must not read as verified),
[[worktree-resolution-canonical-path]].
