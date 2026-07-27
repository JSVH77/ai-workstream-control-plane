#!/usr/bin/env bash
# Control-plane SessionStart hook — re-inject per-worktree state + git orientation.
# stdout is injected into the model's context (resilience pain #5: seamless handover
# after crash/compaction). Keep total output well under ECC's ~8000-char guidance.
# Shared across all worktrees; $CLAUDE_PROJECT_DIR resolves per-worktree.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

echo "=== STREAM STATE (auto-injected at session start) ==="
if [ -f STATE.md ]; then
  head -c 6000 STATE.md
  echo
else
  echo "(no STATE.md in this worktree — create one to seed cross-session handover)"
fi

echo
echo "=== GIT ORIENTATION ==="
echo "worktree: $(pwd)"
echo "branch:   $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [ -n "$upstream" ]; then
  echo "upstream: $upstream"
else
  echo "upstream: (none — branch may be local-only or [gone])"
fi
echo "--- uncommitted (git status -s, top 20) ---"
git status -s 2>/dev/null | head -20
echo "--- recent commits (last 5) ---"
git log --oneline -5 2>/dev/null

echo
echo "=== RECENT JOURNAL (last 8 breadcrumbs) ==="
if [ -f STATE.journal.md ]; then
  tail -n 8 STATE.journal.md
else
  echo "(no STATE.journal.md yet — Stop hook will start appending)"
fi

echo
echo "=== DISPATCH INBOX (unacked cross-stream messages for this stream) ==="
# inbox-peek.py reads the stream id from STATE.md + the canonical .workflow-runtime queue (branch-independent).
# Resolve it next to THIS installed hook (namespace-agnostic — no hardcoded install path).
python3 "$(dirname "${BASH_SOURCE[0]}")/inbox-peek.py" 2>/dev/null || echo "(inbox peek unavailable)"
exit 0
