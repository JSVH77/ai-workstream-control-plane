# `loops/` — loop contracts

One markdown file per loop contract, copied from [`../loop-template.md`](../loop-template.md) and driven
with **`wf loop`** (see spec §3.5). Frontmatter declares the task, the machine-checkable `exit_cmd` (the
independent oracle), the budget (`max_iters`), and the guardrails (`max_unchanged`, `scope`, `scope_slack`).

Contracts are **tracked** (committed + reviewable) — a loop's exit criteria and scope are governance, not
exhaust. The loop's live **lease** (owner / heartbeat / iteration) is the opposite: gitignored runtime under
`.workflow-runtime/leases/<stream>.json`, surfaced by `wf doctor`.

```
wf loop start --contract loops/<name>.md
# each iteration: <do work> ; wf loop tick   (0=continue, 10=done, 20/21/22/23=stop)
wf loop status [--all] ; wf loop release
```
