---
name: worktree-resolution-canonical-path
description: "Any tool mapping streams -> worktrees/buckets MUST derive the canonical <dev_root>/<name> path, never basename-match `git worktree list`. Basenames collide across parent dirs and bind a stream to the wrong checkout. Hit twice, both caught externally."
metadata:
  node_type: memory
  type: feedback
---

**The bug (recurring):** a control-plane tool resolves "which worktree/bucket belongs to stream X" by
taking `git worktree list` entries and matching `os.path.basename(path)` against the registry's `worktree`
field. Development machines accumulate **many same-basename checkouts** under different parents — scratch
clones, review-tool worktrees, `~/.<tool>/worktrees/*/<repo>`. Basename-matching binds a stream to the
**wrong checkout**, so the tool then audits or reports the wrong thing on exactly the multi-worktree
environment it exists to protect.

**The fix — derive the canonical expected path from the registry, don't search for it:**
```python
dev_root = repo_root.parent                      # sibling worktrees live beside the main root
paths = {sid: str(dev_root / v["worktree"]) for sid, v in registry.items() if v.get("worktree")}
```
`<dev_root>/<worktree-name>` is unambiguous and never consumes a colliding scratch entry. If you *do* need
to cross-check against `git worktree list` ("is it git-registered?"), match by **exact path**. If only a
basename matches, at a different parent → flag **AMBIGUOUS** and refuse to guess.

**Incidents (both caught externally, zero self-caught):**
- A recovery/topology tool keyed its worktree map by basename → wrong-checkout binding in the reviewer's
  clone. Fixed with expected-path matching + an AMBIGUOUS flag.
- A memory-hygiene tool later reintroduced the *identical* pattern despite the first fix being in memory —
  textbook **"know-it-but-slip"**.

A related variant: resolving the *main* root by counting parent directories from the script's location
(`__file__.parents[N]`). That yields whichever worktree the script happens to live in. Use
`git rev-parse --git-common-dir` → its parent for the shared/main root, and `--show-toplevel` for the
containing repo.

**Reflex:** writing ANY function that resolves stream → worktree / path / bucket → derive the canonical
path, and grep the new code for `basename(` near worktree/registry logic before pushing. `wf pre-push`
greps for exactly this.

Related: [[name-your-tree-cfr]] (same shape — resolve to a *named*, unambiguous tree).
