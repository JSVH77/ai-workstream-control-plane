#!/usr/bin/env python3
"""control-plane dispatch — the shared append-only cross-stream message bus (control-plane spec §3.3, §7.3).

SA observes + routes; it is NOT the mandatory relay. The QUEUE is the transport: any stream sends an
addressed envelope; the addressee pulls its inbox at its own boundary; SA reads the whole log for
visibility. Envelopes are IMMUTABLE files (append-only); acks are separate marker files — nothing is
ever mutated or deleted, so the log is an audit trail.

Storage is the CANONICAL runtime dir on the MAIN worktree — resolved via `git --git-common-dir` — so
every worktree shares one queue WITHOUT needing the `.workflow-runtime` symlink (that symlink stays
optional, only for other tools that want the dir visible locally). Path: <main-root>/.workflow-runtime/dispatch/

Usage:
  dispatch.py send --from S2 --to SA --type review_request --topic "..." [--refs PR#42 sess:x] [--priority P1]
  dispatch.py inbox --stream S1                 # unacked envelopes addressed to S1 (or to "all")
  dispatch.py watch --stream S1 [--interval N]   # LIVE inbox: long-poll, emit each NEW arrival (one line)
  dispatch.py ack --id <id> --stream S1          # mark an envelope consumed (append-only marker)
  dispatch.py log [--all]                        # SA view: every envelope, chronological, + ack status
  dispatch.py show --id <id>                     # full envelope JSON

`watch` is the Monitor-backed LIVE listener (spec §3.3): run it under the Monitor tool (or `&`) so a
running session reacts to a new envelope WITHOUT a restart — the dispatch analogue of the GitHub
active-listener. It is per-stream on/off by construction: launch it for the stream you want watched, stop
it (TaskStop / kill) to turn it off. It baselines the standing inbox at start (so it never re-fires the
backlog the SessionStart hook already showed) and emits only envelopes that ARRIVE while watching.

Read-only commands (inbox/watch/log/show) never mutate. `send`/`ack` only ever CREATE files.
"""
import subprocess, json, sys, os, argparse, datetime, uuid
from pathlib import Path

def sh(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                              # noqa: E402  (sibling module, script-dir import)

FRAMEWORK = cp.framework_dir(__file__)              # dir containing scripts/ — flat OR vendored
REPO_ROOT = cp.repo_root(FRAMEWORK)

DISPATCH = cp.main_root(REPO_ROOT) / ".workflow-runtime" / "dispatch"
ACKS = DISPATCH / ".acks"

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure():
    ACKS.mkdir(parents=True, exist_ok=True)

def envelopes():
    if not DISPATCH.exists():
        return []
    out = []
    for f in sorted(DISPATCH.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            pass
    return out

def is_acked(eid, stream):
    """Has THIS stream acked? Ack markers are PER-STREAM (<id>__<stream>.json) so a broadcast
    (to: all) is consumed independently by each addressee — not cleared globally by the first ack."""
    return (ACKS / f"{eid}__{stream}.json").exists()

def acks_for(eid):
    """list of {stream, acked_at} — every per-stream ack marker for this envelope."""
    res = []
    for p in ACKS.glob(f"{eid}__*.json"):
        try:
            res.append(json.loads(p.read_text()))
        except Exception:
            pass
    return sorted(res, key=lambda x: x.get("acked_at", ""))

PRI_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

def cmd_send(a):
    ensure()
    eid = now().replace(":", "").replace("-", "") + "-" + uuid.uuid4().hex[:6]
    env = {"id": eid, "from": a.frm, "to": a.to, "type": a.type, "topic": a.topic,
           "refs": a.refs or [], "priority": a.priority, "created_at": now(),
           "lease": None, "ack": None}
    # filename sorts chronologically; envelope is immutable once written
    (DISPATCH / f"{eid}.json").write_text(json.dumps(env, indent=2))
    print(f"sent envelope {eid}  {a.frm} -> {a.to}  [{a.priority}] {a.type}: {a.topic}")

def cmd_inbox(a):
    stream = a.stream
    rows = _inbox_rows(stream)
    if not rows:
        print(f"inbox[{stream}]: empty (no unacked envelopes)")
        return
    print(f"inbox[{stream}]: {len(rows)} unacked")
    for e in rows:
        refs = (" refs=" + ",".join(e["refs"])) if e.get("refs") else ""
        print(f"  {e['id']}  [{e.get('priority')}] {e.get('from')}->{e.get('to')}  {e.get('type')}: {e.get('topic')}{refs}")

def _inbox_rows(stream):
    """Unacked envelopes for a stream (addressed to it or a broadcast), priority-then-time sorted.
    Shared by inbox + watch so the two can't diverge on what counts as 'in the inbox'."""
    rows = [e for e in envelopes()
            if e.get("to") in (stream, "all", "ALL") and not is_acked(e["id"], stream)]
    rows.sort(key=lambda e: (PRI_ORDER.get(e.get("priority"), 9), e.get("created_at", "")))
    return rows

def _fmt_row(stream, e, prefix):
    refs = (" refs=" + ",".join(e["refs"])) if e.get("refs") else ""
    return (f"{prefix} inbox[{stream}] [{e.get('priority')}] {e.get('from')}->{e.get('to')} "
            f"{e.get('type')}: {e.get('topic')}  id={e['id']}{refs}")

def cmd_watch(a):
    """LIVE inbox poll. Emits ONE line per NEW envelope (Monitor turns each into a notification), so a
    running session reacts without a restart. Stdout is flushed per line; poll errors are printed and the
    loop continues (never dies silently on a transient FS/read hiccup — gate-soundness)."""
    import time
    stream, interval = a.stream, max(2, a.interval)
    if a.once:                                   # one-shot dump of the current inbox (testing / scripting)
        rows = _inbox_rows(stream)
        print(f"watch[{stream}] --once: {len(rows)} unacked", flush=True)
        for e in rows:
            print(_fmt_row(stream, e, "NEW"), flush=True)
        return
    # Baseline the standing inbox as already-seen: the SessionStart hook already surfaced it, and a watcher
    # RESTART must not re-fire the whole backlog. Only envelopes that appear AFTER start are emitted.
    seen = {e["id"] for e in _inbox_rows(stream)}
    print(f"watch[{stream}]: live — polling every {interval}s; {len(seen)} already in inbox (baselined, "
          f"not re-fired). Emitting NEW arrivals only. ack: <wf> dispatch ack --id <id> --stream {stream}",
          flush=True)
    while True:
        try:
            for e in _inbox_rows(stream):
                if e["id"] not in seen:
                    seen.add(e["id"])
                    print(_fmt_row(stream, e, "NEW"), flush=True)
        except Exception as ex:                  # never die on a transient read; surface + keep polling
            print(f"watch[{stream}]: poll error (continuing): {ex}", flush=True)
        time.sleep(interval)

def cmd_ack(a):
    ensure()
    match = [e for e in envelopes() if e["id"] == a.id]
    if not match:
        print(f"[!] no envelope with id {a.id}")
        sys.exit(1)
    env = match[0]
    # Delivery integrity: a stream may only ack envelopes addressed TO it (or broadcasts) — not others'.
    if env.get("to") not in (a.stream, "all", "ALL"):
        print(f"[!] envelope {a.id} is addressed to '{env.get('to')}', not '{a.stream}' — refusing ack "
              f"(a stream may only ack its own or broadcast envelopes)")
        sys.exit(1)
    if is_acked(a.id, a.stream):
        print(f"already acked by {a.stream}: {a.id}")
        return
    (ACKS / f"{a.id}__{a.stream}.json").write_text(json.dumps({"stream": a.stream, "acked_at": now()}, indent=2))
    print(f"acked {a.id} by {a.stream}")

def cmd_log(a):
    evs = envelopes()
    if not evs:
        print("dispatch log: empty")
        return
    print(f"dispatch log: {len(evs)} envelopes (chronological)")
    for e in evs:
        acks = acks_for(e["id"])
        status = ("ACKED by " + ",".join(x["stream"] for x in acks)) if acks else "pending"
        refs = (" refs=" + ",".join(e["refs"])) if e.get("refs") else ""
        print(f"  {e.get('created_at')}  {e['id']}  [{e.get('priority')}] {e.get('from')}->{e.get('to')}  "
              f"{e.get('type')}: {e.get('topic')}{refs}  [{status}]")

def cmd_show(a):
    for e in envelopes():
        if e["id"] == a.id:
            print(json.dumps({"envelope": e, "acks": acks_for(a.id)}, indent=2))
            return
    print(f"[!] no envelope with id {a.id}")
    sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog="dispatch")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send"); s.add_argument("--from", dest="frm", required=True)
    s.add_argument("--to", required=True); s.add_argument("--type", required=True)
    s.add_argument("--topic", required=True); s.add_argument("--refs", nargs="*")
    s.add_argument("--priority", default="P2"); s.set_defaults(fn=cmd_send)
    i = sub.add_parser("inbox"); i.add_argument("--stream", required=True); i.set_defaults(fn=cmd_inbox)
    v = sub.add_parser("watch"); v.add_argument("--stream", required=True)
    v.add_argument("--interval", type=int, default=15); v.add_argument("--once", action="store_true")
    v.set_defaults(fn=cmd_watch)
    k = sub.add_parser("ack"); k.add_argument("--id", required=True)
    k.add_argument("--stream", required=True); k.set_defaults(fn=cmd_ack)
    l = sub.add_parser("log"); l.add_argument("--all", action="store_true"); l.set_defaults(fn=cmd_log)
    w = sub.add_parser("show"); w.add_argument("--id", required=True); w.set_defaults(fn=cmd_show)
    a = p.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
