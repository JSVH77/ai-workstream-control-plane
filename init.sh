#!/usr/bin/env bash
# init.sh — day-0 bootstrap for a repo adopting the AI Workstream Control Plane.
#
# Generates the ADOPTER OVERLAY from the shipped `*.example.yaml` templates, then tells you the two
# commands that prove you're operational. It is IDEMPOTENT and NON-DESTRUCTIVE: an existing overlay file
# is never overwritten (it is reported and skipped), because your overlay is the one thing here that is
# genuinely yours.
#
# It does NOT install hooks or write settings — those are `sync-hooks.sh` and `gen-config.py`, run AFTER
# you've edited the overlay. Bootstrapping and configuring are separate on purpose: you must name your
# project before generated artifacts can carry that name.
#
# Usage:   ./init.sh            # from the framework dir (flat repo) or the vendored prefix
#          ./init.sh --memory   # also seed the vendor memory bucket (see step 4 / MEMORY.template.md)
set -euo pipefail

FW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED_MEMORY=0
[ "${1:-}" = "--memory" ] && SEED_MEMORY=1

made=0
copy_example() {
  local src="$1" dst="$2"
  if [ -f "$dst" ]; then
    echo "  [keep]  ${dst#"$FW"/} — already exists, not overwritten"
  elif [ -f "$src" ]; then
    cp "$src" "$dst"; made=$((made + 1))
    echo "  [new]   ${dst#"$FW"/} — from $(basename "$src")"
  else
    echo "  [warn]  missing template $(basename "$src")" >&2
  fi
}

echo "=== control-plane init — generating the adopter overlay in $FW ==="
copy_example "$FW/config/project.example.yaml"   "$FW/config/project.yaml"
copy_example "$FW/config/streams.example.yaml"   "$FW/config/streams.yaml"
copy_example "$FW/config/ownership.example.yaml" "$FW/ownership.yaml"
copy_example "$FW/review-ledger.template.md"     "$FW/review-ledger.md"

# The orchestrator's STATE.md — per-worktree, gitignored (Tier C). Its `**Stream:**` token is the dispatch
# ROUTER key: it MUST equal the registry key, or every envelope to this stream silently goes nowhere.
ROOT="$(git -C "$FW" rev-parse --show-toplevel 2>/dev/null || echo "$FW")"
if [ -f "$ROOT/STATE.md" ]; then
  echo "  [keep]  STATE.md — already exists, not overwritten"
else
  cat > "$ROOT/STATE.md" <<'MD'
# STATE — SA

## Stream identity
- **Stream:** SA
- **Role:** orchestrator — owns the control plane; the ONLY stream that merges (post-review).
- **Lane:** the control-plane files (see `lane` in config/streams.yaml)
- **Base:** main

## Active task
- (set this to what you are doing right now — it is what a restart injects first)

## Governance
- Charter: `charters/SA.md` (apply-authority). Registry: `config/streams.yaml`.

## Open PRs
- (none)

## Next step
- Edit config/project.yaml + config/streams.yaml, then run the readiness gate (see init.sh output).
MD
  made=$((made + 1))
  echo "  [new]   STATE.md — orchestrator (SA) spine at the repo root"
fi

if [ "$SEED_MEMORY" = 1 ]; then
  # The vendor auto-memory bucket is keyed by the MAIN worktree's absolute path; a fresh adopter's bucket
  # is EMPTY, so a new SA starts memory-blind. Seed it from the git-tracked starter set (git is the durable
  # source of truth; the bucket is a thin cache — control-plane-spec §8).
  BUCKET="$HOME/.claude/projects/$(printf '%s' "$ROOT" | tr '/' '-')/memory"
  mkdir -p "$BUCKET"
  echo ""
  echo "--- seeding vendor memory bucket: $BUCKET"
  for f in "$FW"/memory/*.md; do
    b="$(basename "$f")"
    [ "$b" = "README.md" ] && continue
    if [ -f "$BUCKET/$b" ]; then echo "  [keep]  $b"; else cp "$f" "$BUCKET/"; echo "  [new]   $b"; fi
  done
  if [ -f "$BUCKET/MEMORY.md" ]; then
    echo "  [keep]  MEMORY.md (index) — merge the starter pointers by hand if needed"
  else
    cp "$FW/MEMORY.template.md" "$BUCKET/MEMORY.md"; echo "  [new]   MEMORY.md (index, from MEMORY.template.md)"
  fi
fi

cat <<EOF

=== next steps ($made file(s) created) ===
  1. \$EDITOR config/project.yaml     # project_name, hook_namespace, protected_paths, decoupling_nouns
  2. \$EDITOR config/streams.yaml     # one entry per long-lived session; SA keeps can_merge: true
  3. \$EDITOR ownership.yaml          # path-glob -> owning stream (edit-authority)
  4. cp charters/_TEMPLATE.md charters/<ID>.md   # one charter per stream (apply-authority)
  5. git worktree add ../<repo>-<lane> -b <branch> origin/main   # one worktree per non-SA stream
  6. bash scripts/sync-hooks.sh      # install hooks + wf to ~/.claude/hooks/<hook_namespace>/
  7. python3 scripts/gen-config.py   # write each registered worktree's .claude/settings.json

=== then prove it (the readiness bar) ===
  wf doctor --compliance    # every registered stream present · STATE-id == registry · settings == gen-config
  wf smoke                  # a blank repo stands up the whole substrate, in both layouts

Full walkthrough: QUICKSTART.md · use-cases/UC-00-bootstrap-fresh-repo.md
EOF
