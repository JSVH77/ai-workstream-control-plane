---
name: situational-awareness-format
description: "The default shape for a 'where are we / recap / status' answer: one-line state, an ASCII tree of workstreams with status markers, a key-insight paragraph, and an explicit gated-vs-buildable-now split. Prose recaps don't serve this."
metadata:
  node_type: memory
  type: feedback
---

When asked for situational awareness — *"where are we"*, a recap, the big picture, the hierarchy — default
to this shape rather than a prose summary:

1. **One-line "where we are"** at the top: the single most important state fact, with a `◀` marker on the
   active focus.
2. **An ASCII tree of the workstreams**, with:
   - numbered top-level streams (`1. STREAM NAME — IN PROGRESS ◀ you are here`),
   - lettered sub-items (A/B/C…), each with a **status marker**: ✅ done · ⚠️ mixed · ❌ fail · 🔲 to build ·
     🔴 critical finding · ◀ current,
   - dotted leaders and an aligned status column, so it scans vertically,
   - PR numbers / ticket keys inline,
   - a dedicated branch for **decisions open / gating**, and one for **PARKED or SEPARATE** items.
3. **A short "key insight" paragraph** tying the latest event to what it means for the next step.
4. **"What's gated vs buildable now"** — split into decision-gated (waiting on a human ruling), buildable
   without any ruling, and off-critical-path.
5. **End by inviting correction**: "where does this differ from your picture?" — and flag the mental-model
   corrections you think are likeliest.

**Why:** this is for someone holding several parallel workstreams at once — multiple in-flight PRs,
human-gated decisions, parked findings. The tree + status markers + the gated-vs-buildable split is what
gives at-a-glance control. A prose recap forces them to re-derive the structure every time.

**How to apply:** reach for it on any "recap / status / where are we / hierarchy" ask. Keep it **honest**
about the distinctions that matter — committed vs working tree, which branch, started vs blocked, verified
vs assumed (see [[name-your-tree-cfr]]). Those corrections are the most valuable part of the report, not
noise to smooth over.
