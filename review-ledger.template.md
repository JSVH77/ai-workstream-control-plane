# Review-findings ledger + pre-push guard  *(TEMPLATE — `init.sh` copies this to `review-ledger.md`)*

> **Why this exists** (spec §1.1 #5 · §3.6): recurring review findings graduate from prose guidance → a
> **mechanized gate**. Every review finding is logged below; the ones that *recur* distil into the
> **pre-push checklist**; the mechanizable ones run via **`wf pre-push`**.
>
> The pattern this kills: **"know-it-but-slip"** — a finding already learned, caught *externally* rather
> than self-caught. The ledger makes the recurrence visible; the checklist + gate make it preventable.
>
> **This is a template.** The checklist below is the **portable** part — these classes recur in any
> multi-stream AI setup, which is why they ship pre-filled. The findings table is **deliberately empty**:
> it is *your* project's evidence log, and an inherited one would be someone else's history. Append your
> first finding the first time a review catches you.

---

## ⚡ PRE-PUSH CHECKLIST — run before every push

### 🤖 Mechanizable — `wf pre-push` greps your diff for these
- [ ] **Worktree/path resolution.** Any `basename()` near worktree/registry logic? Derive the **canonical**
      path (`<dev_root>/<name>` or `git rev-parse --git-common-dir`), never basename-match `git worktree
      list` — basenames collide across parent dirs and bind a stream to the wrong checkout.
- [ ] **Operator-path hardcoding.** Any literal `/Users/<you>/…` or `-Users-…-slug` presented as
      *universal*? Use a **pattern** + "one observed example".
- [ ] **Born-orphan memory.** New memory file with no index pointer? — run `wf mem-hygiene`.

### 👁 Human-eye — no grep catches these; you must look
- [ ] **Parallel-inconsistency (the #1 repeat).** Fixed a claim / status / value in ONE place? Grep for the
      **same statement elsewhere** — README ↔ spec ↔ tables ↔ help-text ↔ error-hints ↔ sibling docs.
- [ ] **Name-your-tree / memo-as-truth.** Every claim about code or repo state cited at `file:line` on the
      **right tree** (committed vs working; which branch; which worktree)? Prefer symbol anchors to line
      numbers for cross-base refs. Never assert repo state from memory.
- [ ] **Status/date overclaim.** Does a "validated / done" claim's evidence cover the **current**
      documented flow, not an earlier version of it? Does it say *where* it was validated?
- [ ] **Gate-soundness (silence ≠ pass).** Does a guard / gate / check report **pass** when it actually
      *couldn't verify* — an absent worktree, an unresolvable ref, a swallowed subprocess error? Ask: "if
      the thing I'm checking were totally broken or missing, would this still print clean?" If yes, it is
      not a gate.
- [ ] **Stacked-PR order.** Retarget upper PRs to the final base **before** merging the stack parent —
      and remember `--delete-branch` on a parent auto-closes children based on it (unreopenable).
- [ ] **Sign-off.** PR / issue / review comment signed `— [<stream>/<role>]`?
- [ ] `<add your project's recurring classes here as they earn a row>`

---

## 📒 FINDINGS LEDGER — append every review/operator finding

Columns: **class** links to the checklist row it belongs to (or `NEW` if it's a first occurrence to watch).

| date | PR | by | sev | class | finding → fix |
|---|---|---|---|---|---|
| | | | | | *(empty — append your first finding here)* |

**Recurrence tally:** *(count rows per class as they accumulate; a class at ≥2 needs a checklist row, and
at ≥3 — or any deterministic drift with a cheap mechanical check — it should become a gate. §3.6.)*

> **How to use:** append each new finding as it lands (one row). When a class hits **2**, ensure it has a
> checklist row; at **3**, mechanize it (a `wf pre-push` check, a lint, a CI gate). Track how many findings
> were **self-caught before push** vs. caught externally — that ratio is the honest measure of whether the
> loop is working, and the reason to mechanize rather than remember.
