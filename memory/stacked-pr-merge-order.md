---
name: stacked-pr-merge-order
description: "In a PR stack A->B->C, retarget the children to the final base BEFORE merging the parent. And `gh pr merge <parent> --delete-branch` AUTO-CLOSES children based on that branch — unreopenable, because their base is gone."
metadata:
  node_type: memory
  type: feedback
---

**The rule:** when PRs are stacked (B's base is A's branch, C's base is B's branch), **retarget B and C to
the final destination branch before merging A.**

**Two distinct ways this bites:**

**1. The child stays cosmetically OPEN forever.** GitHub's auto-close trigger only fires when a PR's HEAD
becomes reachable from *that PR's own base branch*. If the child's base is still the parent's branch —
frozen at its pre-merge state — merging everything into the final target closes the parent and leaves the
child open, with its work already shipped. Trying to fix it afterwards fails: `gh api -X PATCH … -f base=…`
returns **422 "no new commits between base and head"**, because the target already contains the child's
content, so there is no diff left to display. The PR then has to be closed by hand.

**2. `--delete-branch` silently closes the children.** `gh pr merge <parent> --delete-branch` deletes the
parent's branch — and GitHub **auto-closes every PR whose base was that branch**. Those PRs **cannot be
reopened**, because their base no longer exists. Their work is not merged; it is orphaned behind a closed,
un-reopenable PR.

**How to apply — before merging any stack parent:**
1. Detect the stack: `gh pr list --base <parent-branch>` — anything returned is stacked on it.
2. Rebase each child onto the final target, skipping the parent's commits:
   `git rebase --onto origin/<final-target> <parent-tip-sha> <child-branch>`
   (a vanilla rebase conflicts on commits already present via the parent's squash — same content, new SHA).
3. Retarget each child: `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -f base=<final-target>`.
   This works only while parent and target still differ — i.e. **before** the merge.
4. *Then* merge the stack in order. Each child's auto-close fires correctly against its own (now correct)
   base. Only use `--delete-branch` on a parent once no PR targets it.

**Recovery if you forgot:** try the retarget (fails 422 once the content is already in the target); if the
child was auto-closed by a branch deletion, the branch and PR are unrecoverable as-is — re-open the work as
a **new** PR from a restored branch (`git push origin <local-sha>:refs/heads/<branch>`), and say in the body
what happened, so the audit trail isn't a mystery.
