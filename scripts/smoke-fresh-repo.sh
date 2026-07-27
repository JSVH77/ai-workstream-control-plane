#!/usr/bin/env bash
# smoke-fresh-repo — behavioral genericity gate for the framework.
#
# WHY: decoupling-lint proves the core carries no host-project NOUNS (a grep — which can false-green). This
# proves the harder thing BEHAVIORALLY: a BLANK repo, given only the framework core + a generic project
# config (no host nouns), can actually STAND UP and RUN the substrate. "Generic" is only real if a fresh
# host can bootstrap and operate it.
#
# LAYOUT MATRIX (added in the E2 extraction): the framework supports TWO installs — flat (the framework IS
# the repo) and vendored (`git subtree --prefix=X`). A layout assumption that regressed would otherwise pass
# whichever single shape the harness happened to build, so we stand the substrate up in BOTH and require
# both green. That is what makes "layout-agnostic" a gate rather than a claim.
#
# ISOLATED: runs in throwaway temp repos AND a temp $HOME, so it never touches the operator's ~/.claude
# (sync-hooks / mem-hygiene write under $HOME). Everything is cleaned up on exit. Read-only w.r.t. the repo
# it ships in. Exit 0 = every layout stood up the substrate; non-zero = one did not.
#
# Usage:  scripts/smoke-fresh-repo.sh   |   wf smoke
set -uo pipefail

FRAMEWORK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # this repo's framework dir
TMP="$(mktemp -d)"; HOMEDIR="$TMP/home"
mkdir -p "$HOMEDIR"
cleanup(){ rm -rf "$TMP"; }
trap cleanup EXIT

fail=0
pass(){ printf '  [PASS] %s\n' "$1"; }
bad(){  printf '  [FAIL] %s\n' "$1"; fail=1; }
check(){ local name="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$name"; else bad "$name"; fi; }

# run_layout <label> <prefix>
#   prefix ""         -> flat     (<repo>/scripts/…)
#   prefix "vendored" -> vendored (<repo>/vendored/scripts/…)
# A NON-"workflow" prefix is used deliberately: it would catch any lingering hardcode of the old
# `workflow/` path layer, which a `workflow` prefix would silently satisfy.
run_layout() {
  local label="$1" prefix="$2"
  local repo="$TMP/repo-${label}" fw
  if [ -n "$prefix" ]; then fw="$repo/$prefix"; else fw="$repo"; fi
  mkdir -p "$repo"

  echo ""
  echo "--- layout: $label  (framework at ${prefix:-<repo root>}) ---"

  # 1. a fresh git repo (single worktree = the common case for a new project)
  git -C "$repo" init -q
  git -C "$repo" config user.email smoke@test.local
  git -C "$repo" config user.name  "smoke"

  # 2. drop in the framework CORE (scripts + hooks + the generic settings floor + templates)
  mkdir -p "$fw/config" "$fw/loops"
  cp -R "$FRAMEWORK/scripts" "$FRAMEWORK/hooks" "$fw/"
  rm -rf "$fw/scripts/__pycache__"
  cp "$FRAMEWORK/config/settings-base.json" "$fw/config/"
  cp "$FRAMEWORK/loop-template.md" "$fw/" 2>/dev/null || true
  cp "$FRAMEWORK/loops/README.md"  "$fw/loops/" 2>/dev/null || true

  # 3. FRESH project overlay — DOGFOOD the shipped example template (so a bad example config can't pass
  # smoke, e.g. a default decoupling_noun that collides with the core's own examples). streams stays
  # inline: the example registry names worktrees that don't exist here, but compliance needs a resolvable
  # one. The lane is written to match THIS layout, so the fixture stays honest about where the core lives.
  cp "$FRAMEWORK/config/project.example.yaml" "$fw/config/project.yaml"   # MyProject / myproject
  cat > "$fw/config/streams.yaml" <<YAML
streams:
  SA:
    worktree: repo-${label}
    role: orchestrator
    lane: ["${prefix:+$prefix/}**"]
    base: main
    can_merge: true
YAML
  cat > "$repo/STATE.md" <<'MD'
# STATE — SA
## Stream identity
- **Stream:** SA
MD
  # The two .gitignore rules every adopter needs (spec §1.2 tracked-vs-runtime + Python bytecode). Part of
  # the fixture because a fresh repo genuinely starts with them — and because `wf` fails closed on a dirty
  # framework dir, so an un-ignored artifact is an operational problem, not cosmetics.
  cat > "$repo/.gitignore" <<'MD'
.workflow-runtime/
__pycache__/
STATE.md
STATE.journal.md
MD
  git -C "$repo" add -A && git -C "$repo" commit -qm "bootstrap" && git -C "$repo" branch -M main

  # 4. run the substrate. HOME override => sync-hooks / mem-hygiene stay inside the sandbox.
  # cd into the fresh repo (no subshell — a subshell would sandbox $fail and never propagate the verdict).
  export HOME="$HOMEDIR"
  local S="$fw/scripts"
  cd "$repo"
  check "doctor runs"                    python3 "$S/doctor.py"
  check "decoupling-lint core clean"     python3 "$S/decoupling-lint.py" --zone core
  check "gen-config --dry-run (preview)" python3 "$S/gen-config.py" --dry-run
  # APPLY gen-config, THEN require compliance to PASS strictly — the harness must prove the fresh repo
  # reaches the control-plane's own pre-operationalize READY bar, not merely that the commands execute.
  check "gen-config apply (writes settings)" python3 "$S/gen-config.py"
  check "doctor --compliance PASSES (ready)" python3 "$S/doctor.py" --compliance
  check "mem-hygiene runs"               python3 "$S/mem-hygiene.py"
  check "pre-push guard runs"            python3 "$S/pre-push-check.py"
  check "dispatch send"                  python3 "$S/dispatch.py" send --from SA --to SA --type smoke --topic "hello fresh repo" --priority P3
  check "dispatch inbox"                 python3 "$S/dispatch.py" inbox --stream SA
  local eid
  eid="$(python3 "$S/dispatch.py" inbox --stream SA 2>/dev/null | grep -oE '[0-9]{8}T[0-9]{6}Z-[0-9a-f]+' | head -1)"
  check "dispatch ack"                   python3 "$S/dispatch.py" ack --id "$eid" --stream SA
  check "loop status"                    python3 "$S/loop.py" status --all
  check "sync-hooks (sandbox HOME)"      bash "$S/sync-hooks.sh"
  # namespace = hook_namespace from the example project.yaml (myproject)
  check "hooks installed to namespace"   test -f "$HOMEDIR/.claude/hooks/myproject/session-start.sh"
  check "wf launcher installed"          test -f "$HOMEDIR/.claude/hooks/myproject/wf"
  # The launcher must find the framework from the repo in THIS layout (the layout-agnostic resolution).
  check "wf resolves framework (any layout)" bash "$HOMEDIR/.claude/hooks/myproject/wf" doctor
  rm -rf "$HOMEDIR/.claude"      # reset the sandbox HOME between layouts
}

echo "=== smoke-fresh-repo: stand up the control-plane substrate on a BLANK repo (both layouts) ==="
run_layout flat     ""
run_layout vendored "vendored"

echo ""
if [ "$fail" = 0 ]; then
  echo "✅ a blank repo stood up the substrate with generic config, in BOTH layouts —"
  echo "   framework is behaviorally generic AND layout-agnostic"
else
  echo "❌ smoke failed — the substrate did not stand up cleanly on a fresh repo"
fi
exit "$fail"
