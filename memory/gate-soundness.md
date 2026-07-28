---
name: gate-soundness
description: "A check that cannot verify its subject must FAIL or warn loudly — never print clean. Ask: 'if the thing I'm checking were totally broken or missing, would this still report pass?' If yes, it isn't a gate."
metadata:
  node_type: memory
  type: feedback
---

**The rule:** silence is never a pass. Any guard, gate, report, or health check that could not actually
evaluate its subject must **warn loudly or exit non-zero**. A green result must mean "I checked, and it was
fine" — never "I couldn't check."

**The test to apply to every check you write:**
> *If the thing I'm checking were completely broken, absent, or unreachable — would this still print clean?*

If the answer is yes, you have written a **false-green**, not a gate.

**Real incidents this comes from:**
- A compliance gate iterated the registry and validated each stream *that was present*. On a machine with
  **none** of the streams checked out it validated nothing and exited **0** — green-lighting an environment
  that had nothing to green-light. Fix: an absent or ambiguous target is itself a **FAIL**.
- A pre-push guard shelled out to `git diff <base>` and treated a **failed** command the same as **empty
  output**. When the base ref wasn't fetched locally, "0 changed files, no findings" — a clean bill of
  health for a diff that was never computed. Fix: the subprocess wrapper distinguishes *failure* from
  *empty*, and the tool prints a loud `BASE UNRESOLVED` banner.
- A decoupling lint derived its forbidden-token set from config. With no config it had an empty set,
  matched nothing, and passed. Fix: an empty rule set on a gated run **exits 2** — no config, no gate.
- A loop engine's exit oracle: a missing or timed-out `exit_cmd` is **not** a "not done yet" verdict. It
  must fail **closed** (stop the loop), never read as "keep going."

**How to apply:**
1. Wrap subprocess calls so callers can tell `None` (failed) from `""` (succeeded, no output). Never let
   an exception collapse into a falsy "clean" value.
2. For every gate, enumerate the ways it could be *unable* to check, and make each one loud.
3. Prefer exit codes that distinguish "verified bad" from "couldn't verify" — they call for different
   human responses.
4. When you fix a false-green, add the class to the pre-push checklist; it recurs.

Related: [[name-your-tree-cfr]] (the reporting analogue — an unverified claim must not read as verified).
