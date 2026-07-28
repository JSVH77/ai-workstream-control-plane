#!/usr/bin/env bash
# Install the tracked canonical hooks (the framework's hooks/) into the live shared location used by every
# worktree: ~/.claude/hooks/<hook_namespace>/ (branch-independent). Run this after changing hooks/*.
# The hooks live outside the repo (operator environment) so a fresh clone/worktree still fires them;
# the framework's hooks/ is the version-controlled source of truth, this script is the one-way sync.
# Idempotent. Paths here are resolved RELATIVE to this script, so it works in either layout (framework at
# the repo root, or vendored under a `git subtree` prefix).
# <hook_namespace> comes from config/project.yaml — the framework core is project-agnostic.
set -euo pipefail
HOOKS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../hooks" && pwd)"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS="$(grep -E '^hook_namespace:' "$SCRIPTS/../config/project.yaml" | head -1 | sed -E 's/^hook_namespace:[[:space:]]*//; s/["'"'"']//g; s/[[:space:]]*(#.*)?$//')"
[ -n "$NS" ] || { echo "sync-hooks: no hook_namespace in config/project.yaml" >&2; exit 1; }
DST="$HOME/.claude/hooks/$NS"
mkdir -p "$DST"
# hooks
cp "$HOOKS/session-start.sh" "$HOOKS/stop-journal.sh" "$HOOKS/pre-compact.sh" "$HOOKS/inbox-peek.py" "$DST/"
chmod +x "$DST/session-start.sh" "$DST/stop-journal.sh" "$DST/pre-compact.sh"
# wf launcher — lets any stream run the tools branch-independently (it re-resolves the main worktree,
# so it does not need the .py tools copied here; they always live in the main worktree's framework dir).
cp "$SCRIPTS/wf" "$DST/"
chmod +x "$DST/wf"
echo "synced canonical hooks + wf launcher -> $DST"
echo "  (add $DST to PATH, or call: $DST/wf dispatch inbox --stream <id>)"
ls -1 "$DST"
