---
name: external-review-monitor
description: "Why a 'watch for the review to land' monitor silently never fires: it filters on the author login (external reviewers often post as a human account, not a bot) and it windows on timestamps. Filter on BODY, baseline on comment ID, and arm it before the push."
metadata:
  node_type: memory
  type: feedback
---

**Symptom:** you arm a `Monitor` / poll loop to catch an external review landing on a PR, and it **never
fires**. The operator ends up prompting "check the reviews" — repeatedly.

**Two root causes; the first is the real one.**

**1. Author-login filtering doesn't match.** An external review tool often posts through a *human* account
(the integration runs as the repo owner), not a recognizable bot login. A filter like
`select(.user.login | test("bot|codex|copilot|github-actions"; "i"))` therefore matches **nothing**, and
every real review comment is filtered out. **Fix: filter on the comment BODY, not the author** — review
comments carry a stable signature (a tool's sign-off line, a `Findings:` header, `Review on current head
<sha>`). Body patterns survive an account change; login patterns don't.

**2. Timestamp windows drop events at the edges.** Seeding a poll with `since=<timestamp>` keeps missing
comments, because the monitor gets armed *after* other work and the review lands in the gap, or exactly on
a window boundary. Back-dating `since` is a band-aid. **Fix: baseline on comment ID, not time.** At arm
time record `max(.id)` for the PR; each poll emits only `.id > baseline`, then advances the baseline. IDs
are monotonic and have no edges.

```bash
# arm: baseline = highest existing comment id
base=$(gh api "repos/<owner>/<repo>/issues/<PR>/comments" --jq '[.[].id] | max // 0')
# poll: new comments only, filtered by BODY
gh api "repos/<owner>/<repo>/issues/<PR>/comments" \
  --jq --argjson b "$base" '.[] | select(.id > $b) | select(.body | test("<review-signature>")) | .body[0:400]'
```
Also poll `pulls/<PR>/reviews` — formal reviews are a different endpoint from issue comments.

**Residual limits (accept them, don't paper over them):**
- A monitor can't catch a review that landed **before** it was armed. Arm it right after the push, and do
  one manual `gh pr view` for anything already in flight.
- On macOS's default bash 3.2 there are **no associative arrays** — use plain per-PR variables.

**Verdict discipline:** know your reviewer's exact "clean" phrasing and match it literally; do not infer a
pass from the absence of findings — an empty poll result usually means the *poll* failed, not that the
review was clean. See [[gate-soundness]].
