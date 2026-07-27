#!/usr/bin/env python3
"""Dispatch inbox peek for the SessionStart hook (control-plane spec §3.3).

Prints the unacked dispatch envelopes addressed to THIS stream, so a stream sees its pending
cross-stream messages the moment its session starts. Read-only.

Branch-independent by design — depends only on things always present regardless of the checked-out
branch: (1) the per-worktree STATE.md (for the stream id), and (2) the canonical gitignored
.workflow-runtime/dispatch/ (resolved via git-common-dir). It does NOT import the framework's dispatch.py,
which may not be on the local branch. Run from the worktree root (the hook cd's there first).
"""
import json, re, subprocess
from pathlib import Path

PRI = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

def stream_id():
    try:
        for line in Path("STATE.md").read_text().splitlines():
            m = re.search(r"\*\*Stream:\*\*\s*([A-Za-z0-9/_-]+)", line)
            if m:
                return m.group(1).strip().rstrip(".")
    except Exception:
        pass
    return None

def dispatch_dir():
    try:
        cd = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                            capture_output=True, text=True, timeout=10).stdout.strip()
        if not cd:
            return None
        p = Path(cd)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return p.parent / ".workflow-runtime" / "dispatch"
    except Exception:
        return None

def main():
    sid = stream_id()
    if not sid:
        print("(no stream id in STATE.md — skipping inbox)")
        return
    disp = dispatch_dir()
    if not disp or not disp.exists():
        print(f"inbox[{sid}]: empty (queue not initialized)")
        return
    acks = disp / ".acks"
    rows = []
    for f in sorted(disp.glob("*.json")):
        try:
            e = json.loads(f.read_text())
        except Exception:
            continue
        if e.get("to") in (sid, "all", "ALL") and not (acks / f"{e['id']}__{sid}.json").exists():
            rows.append(e)
    if not rows:
        print(f"inbox[{sid}]: empty")
        return
    rows.sort(key=lambda e: (PRI.get(e.get("priority"), 9), e.get("created_at", "")))
    wf = Path(__file__).resolve().parent / "wf"    # the wf launcher installed beside this hook (namespace-agnostic)
    print(f"inbox[{sid}]: {len(rows)} UNACKED — ack via  {wf} dispatch ack --id <id> --stream {sid}")
    for e in rows:
        refs = (" refs=" + ",".join(e["refs"])) if e.get("refs") else ""
        print(f"  {e['id']}  [{e.get('priority')}]  {e.get('from')}->{e.get('to')}  {e.get('type')}: {e.get('topic')}{refs}")

if __name__ == "__main__":
    main()
