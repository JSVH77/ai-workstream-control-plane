#!/usr/bin/env bash
# Control-plane Stop hook — append a cheap git breadcrumb after each agent turn.
# No LLM involvement: just timestamp + branch@HEAD + dirty count, so a crashed
# session leaves a recovery trail. Trimmed to the last 200 lines to stay bounded.
# Shared across all worktrees; $CLAUDE_PROJECT_DIR resolves per-worktree.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

ts="$(date '+%Y-%m-%d %H:%M:%S')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
head="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
dirty="$(git status -s 2>/dev/null | wc -l | tr -d ' ')"

echo "- ${ts} | ${branch} @ ${head} | ${dirty} dirty" >> STATE.journal.md

# Bound the journal: keep last 200 entries.
if [ "$(wc -l < STATE.journal.md 2>/dev/null || echo 0)" -gt 200 ]; then
  tail -n 200 STATE.journal.md > STATE.journal.md.tmp && mv STATE.journal.md.tmp STATE.journal.md
fi
exit 0
