# QUICKSTART — stand up the control plane in a fresh repo

Day-0 setup for a new project. ~10 minutes. Validate the whole thing at the end with `wf smoke`.

> **Concepts first?** Read [`README.md`](README.md) (the seven pieces) — this is the hands-on version.

## 0. Install the framework

Either layout works — nothing in the core assumes one (spec §1.3):

```bash
# A · standalone: clone/copy this repo, work in it
# B · vendored into an existing repo, under any prefix you like:
git subtree add --prefix=workflow <this-repo-url> main --squash
```

Add these to your repo's `.gitignore`: `.workflow-runtime/`, `__pycache__/`, `STATE.md`, `STATE.journal.md`.
(`wf` refuses to run with a dirty framework dir, so an un-ignored artifact is an operational problem.)

## 1. Name your project

```bash
./init.sh --memory      # generates the overlay from the examples + seeds the memory bucket
$EDITOR config/project.yaml       # project_name, hook_namespace, protected_paths, decoupling_nouns
```

`init.sh` is idempotent and never overwrites an existing file. `project.yaml` is the ONE file that names
your project — the framework core reads its identity from here.

## 2. Define your streams

Edit `config/streams.yaml`: one entry per long-lived session, separated by **file lane** (not by
branch). Keep **SA** (orchestrator, `can_merge: true`) on the main root; give each other stream its own
worktree dir + a `lane`. Point each `governs:` at a charter you mint next.

```bash
git worktree add ../myproject-fe   -b feature/fe-init origin/main   # one worktree per non-SA stream
```

Also edit `ownership.yaml` (path-glob → owning stream: **edit**-authority, the dual of the charter).

## 3. Mint charters (apply-authority)

`init.sh` already rendered **`charters/SA.md`** from the shipped `SA.template.md` startup-kit charter —
adopt it as-is and add your project's merge gates where marked. That concrete charter is **yours**: core
ships only the template, so an upstream `git subtree pull` can never clobber your merge gates. (Vendored
installs: `git add -f charters/SA.md` once — see the README warning.)

Then mint one charter per **additional** stream:

```bash
cp charters/_TEMPLATE.md charters/S1.md   # repeat per stream; fill in
```

> **SA's charter says "merge post-review only" — that needs a reviewer to be satisfiable.** Onboard one
> via [`use-cases/UC-01`](use-cases/UC-01-onboard-stream.md) (start from `charters/CR.template.md`), or
> amend your `SA.md` deliberately. Don't leave SA charter-blocked with no reviewer to unblock it.

## 4. Install the hooks + generate settings

```bash
bash scripts/sync-hooks.sh          # installs hooks + wf to ~/.claude/hooks/<hook_namespace>/
python3 scripts/gen-config.py       # writes each registered worktree's .claude/settings.json
```

Add `~/.claude/hooks/<hook_namespace>/` to your PATH so `wf` is available everywhere (or call it by full path).

> ### ⚠ The bootstrap session is pre-floor — restart it
>
> **Settings load at session START.** The session in which you cloned the repo and ran `init.sh` is running
> on your **global** permissions: no project floor, none of the `rm -rf /` · force-push · `sudo` denies, no
> hook wiring. Nothing that runs *during* that session can change this.
>
> - This repo ships a **committed baseline** `.claude/settings.json` (the generic floor), so a fresh clone
>   has the safety denies from the start — but a session already running when the file appears won't see it.
> - `init.sh` writes/refreshes the floor and runs `gen-config` for you, then prints a restart notice.
> - **Restart the session** after `sync-hooks` + `gen-config`. Then the floor and hooks are live.
>
> **`.claude/settings.json` is generated** — `gen-config` overwrites it. Put your personal, machine-specific
> allows in **`.claude/settings.local.json`** instead: it is gitignored and `gen-config` never touches it.
> Once `gen-config` has run, `settings.json` will normally show as *modified* against the committed
> baseline. That is expected (spec §3.7) — don't commit your specialized copy over the baseline, or you
> push your worktree's merge policy onto every other stream.

## 5. Seed each worktree's STATE.md

Each worktree needs a `STATE.md` whose header names the stream (the hooks + router read it):

```markdown
# STATE — SA
## Stream identity
- **Stream:** SA
```

## 6. Validate — the readiness gate

```bash
wf doctor --compliance     # every registered stream: present · STATE-id == registry · settings == gen-config
wf smoke                   # end-to-end: a blank repo can stand up the whole substrate (behavioral gate)
```

Green on both = you're operational. Then, per stream: start a Claude Code session in its worktree — the
SessionStart hook auto-injects its STATE + git orientation + dispatch inbox.

## Everyday commands

```bash
wf doctor                              # topology + health across all streams
wf dispatch send --from S1 --to SA --type review_request --topic "PR #42 ready" --refs PR#42
wf dispatch inbox --stream SA          # (auto-shown at SessionStart; wf dispatch watch for a live listener)
wf loop start --contract loops/<name>.md   # safe fix-until-green loops (see loop-template.md)
wf pre-push                            # advisory guard for recurring review classes before you push
```

Full model + rationale: [`control-plane-spec.md`](control-plane-spec.md). Recovery drill:
[`DISASTER-RECOVERY.md`](DISASTER-RECOVERY.md). Onboarding a stream later: [`use-cases/UC-01-onboard-stream.md`](use-cases/UC-01-onboard-stream.md).
