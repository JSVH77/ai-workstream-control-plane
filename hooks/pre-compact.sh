#!/usr/bin/env bash
# Control-plane PreCompact hook — back up the transcript before compaction summarizes
# (and loses) early context. Reads the hook payload from stdin; transcript_path is
# the live JSONL session log. Anthropic won't let a hook *write* a handoff at
# compaction (issue #43733, "not planned"), so we preserve the raw transcript instead.
# Shared across all worktrees; $CLAUDE_PROJECT_DIR resolves per-worktree.
# Uses python3 (not jq — jq is not guaranteed installed on this machine).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

input="$(cat || true)"
read -r tp trigger < <(printf '%s' "$input" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); sys.exit(0)
print(d.get("transcript_path", ""), d.get("trigger", "unknown"))
' 2>/dev/null || echo "")

[ -z "${tp:-}" ] && exit 0
[ ! -f "$tp" ] && exit 0

mkdir -p .claude/transcript-backups
ts="$(date '+%Y%m%d-%H%M%S')"
cp "$tp" ".claude/transcript-backups/precompact-${trigger:-unknown}-${ts}.jsonl" 2>/dev/null || true

# Bound: keep the 10 most-recent backups.
ls -1t .claude/transcript-backups/precompact-*.jsonl 2>/dev/null \
  | tail -n +11 | while read -r old; do rm -f "$old"; done
exit 0
