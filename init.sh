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
# SA's concrete charter (apply-authority). Core ships templates only so an upstream subtree pull can never
# clobber a host's own merge gates — see the charters block in .gitignore.
# Deliberately NOT rendering charters/CR.md here: the shipped registry defines no CR stream, so a rendered
# CR.md would be a charter for a stream `doctor --compliance` never checks and `decoupling-lint`'s overlay
# zone never scans (it derives charters FROM the registry). UC-01 mints it when you onboard a reviewer.
copy_example "$FW/charters/SA.template.md"       "$FW/charters/SA.md"

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

# --- the settings FLOOR — closes the bootstrap window --------------------------------------------
# Chicken-and-egg: `.claude/settings.json` is what carries the permission floor (the rm -rf / force-push /
# sudo denies + hook wiring), but settings load at session START. A session that clones and runs this script
# is therefore running on the operator's GLOBAL permissions, with no project floor, until it restarts.
#
# Two layers close it:
#   1. this repo ships a COMMITTED baseline `.claude/settings.json` (the generic floor with the namespace
#      resolved), so the denies are active from `git clone` — before this script has ever run;
#   2. below, we render the floor for any repo that lacks one (an adopter vendoring the framework into their
#      own repo has no baseline of ours), then run gen-config to SPECIALIZE it per registered worktree.
# Neither layer can help the CURRENT session — settings are read once, at start. Hence the restart notice.
echo ""
echo "--- settings floor"
NS="$(grep -E '^hook_namespace:' "$FW/config/project.yaml" 2>/dev/null | head -1 \
      | sed -E 's/^hook_namespace:[[:space:]]*//; s/["'"'"']//g; s/[[:space:]]*(#.*)?$//')"
if [ -z "$NS" ]; then
  echo "  [warn]  no hook_namespace in config/project.yaml — skipping floor; set it, then re-run" >&2
elif [ -f "$ROOT/.claude/settings.json" ]; then
  echo "  [keep]  .claude/settings.json — already present, not overwritten"
else
  mkdir -p "$ROOT/.claude"
  python3 -c 'import sys,pathlib; src,dst,ns = sys.argv[1:4]; \
pathlib.Path(dst).write_text(pathlib.Path(src).read_text().replace("{{HOOK_NAMESPACE}}", ns))' \
    "$FW/config/settings-base.json" "$ROOT/.claude/settings.json" "$NS"
  echo "  [new]   .claude/settings.json — generic floor, hook_namespace=$NS"
fi
# Specialize per registered worktree (adds protected_paths/extra_denies + the per-stream merge policy).
# Streams whose worktree isn't created yet are reported as [skip] — re-run gen-config after adding them.
python3 "$FW/scripts/gen-config.py" || echo "  [warn]  gen-config did not complete — run it after editing the overlay" >&2

cat <<EOF

⚠  RESTART this Claude Code session to load .claude/settings.json — settings are read at session START,
   so the session that ran this script is still on your global permissions, with no project floor.

=== next steps ($made file(s) created) ===
  1. \$EDITOR config/project.yaml     # project_name, hook_namespace, protected_paths, decoupling_nouns
  2. \$EDITOR config/streams.yaml     # one entry per long-lived session; SA keeps can_merge: true
  3. \$EDITOR ownership.yaml          # path-glob -> owning stream (edit-authority)
  4. \$EDITOR charters/SA.md                     # rendered above from SA.template.md — add your gates
     cp charters/_TEMPLATE.md charters/<ID>.md   # one charter per ADDITIONAL stream (apply-authority)
     # NB: SA.md ships "merge post-review only" — that needs a REVIEWER to be satisfiable.
     # Onboard one via use-cases/UC-01 (charters/CR.template.md is the starting point), or
     # amend your SA.md deliberately. Don't leave SA charter-blocked with no reviewer.
  5. git worktree add ../<repo>-<lane> -b <branch> origin/main   # one worktree per non-SA stream
  6. bash scripts/sync-hooks.sh      # install hooks + wf to ~/.claude/hooks/<hook_namespace>/
  7. python3 scripts/gen-config.py   # re-run after 1-5: regenerates each worktree's .claude/settings.json

  (Personal per-worktree overrides go in .claude/settings.local.json — gitignored, and gen-config NEVER
   touches it. Put machine-specific allows there, not in settings.json, which is generated.)

=== then prove it (the readiness bar) ===
  wf doctor --compliance    # every registered stream present · STATE-id == registry · settings == gen-config
  wf smoke                  # a blank repo stands up the whole substrate, in both layouts

Full walkthrough: QUICKSTART.md · use-cases/UC-00-bootstrap-fresh-repo.md
EOF
