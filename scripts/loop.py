#!/usr/bin/env python3
"""control-plane loop — the deterministic loop-contract engine (control-plane spec §3.5).

Looping is safe ONLY when an EXTERNAL, deterministic thing owns the exit decision — never the agent
grading its own work in the same lane (§3.5 guardrail #1, "independent oracle"). This engine is that
thing. It does NOT drive the LLM; the WORKER (a stream agent, or a `ralph` bash `while`-loop) does one
iteration of work, then calls `loop tick`, which owns the LEASE + EXIT-CHECK + GUARDRAILS and returns
CONTINUE / STOP.

Flow:
  loop start --contract <file>     # validate, acquire a lease (refuses if one is already live)
  <worker does one iteration>
  loop tick                        # heartbeat; run exit_cmd; enforce guardrails; verdict
  ... repeat while tick says continue ...
  loop status | loop release       # inspect | end

`tick` EXIT CODES (so a bash `ralph` loop can `<do-work> && wf loop tick || break`):
  0  = CONTINUE (exit not yet met, no guardrail tripped)
  10 = STOP: exit met  ✅  (open a PR — the loop NEVER merges; SA-only merge stays)
  20 = STOP: budget (max_iters)      21 = STOP: stuck (max_unchanged)      22 = STOP: scope brake
  23 = STOP: oracle unavailable (exit_cmd couldn't run — timeout / missing binary; fail closed, not continue)
An agent worker reads the printed verdict; a bash worker keys off the code.

Contract file = markdown with YAML frontmatter (required: task, exit_cmd, max_iters):
  ---
  task: "Make the failing suite green"
  exit_cmd: "python -m pytest -q tests/"        # MUST return 0/1; else don't loop
  max_iters: 8
  max_unchanged: 2            # flat diff / same failing check this many times -> stop (default 2)
  scope: ["src/**"]          # globs the loop may touch; anything else -> scope brake
  scope_slack: 0             # files allowed outside scope before braking (default 0)
  exit_timeout_s: 600        # kill a hung exit_cmd (default 600)
  cost_note: "~$2/iter; hard cap 8 iters"
  ---
  (free-text acceptance detail)

Lease = <main-root>/.workflow-runtime/leases/<stream>.json (gitignored runtime, canonical main-root via
git-common-dir — same convention as dispatch.py). ONE live loop per stream. `doctor` surfaces stale leases.
MUTATES only the lease + its journal; runs your exit_cmd; never commits, never merges.
"""
import subprocess, json, sys, os, argparse, datetime, re, hashlib
from pathlib import Path

def sh(args, cwd=None, timeout=30):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                              # noqa: E402  (sibling module, script-dir import)

FRAMEWORK = cp.framework_dir(__file__)              # dir containing scripts/ — flat OR vendored
REPO_ROOT = cp.repo_root(FRAMEWORK)

LEASES = cp.main_root(REPO_ROOT) / ".workflow-runtime" / "leases"

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def stream_id(explicit=None):
    """--stream wins; else the worktree's STATE.md `**Stream:**` token (same regex inbox-peek/doctor use)."""
    if explicit:
        return explicit
    try:
        for line in (Path.cwd() / "STATE.md").read_text().splitlines():
            m = re.search(r"\*\*Stream:\*\*\s*([A-Za-z0-9/_-]+)", line)
            if m:
                return m.group(1).strip().rstrip(".")
    except Exception:
        pass
    return None

def lease_path(sid):
    return LEASES / f"{sid}.json"

def load_lease(sid):
    p = lease_path(sid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def save_lease(sid, lease):
    LEASES.mkdir(parents=True, exist_ok=True)
    lease_path(sid).write_text(json.dumps(lease, indent=2))

def parse_contract(path):
    text = Path(path).read_text()
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None, "no YAML frontmatter (--- ... ---) found"
    try:
        import yaml
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception as e:
        return None, f"frontmatter is not valid YAML: {e}"
    for req in ("task", "exit_cmd", "max_iters"):
        if not meta.get(req):
            return None, f"missing required field: {req}"
    if not str(meta.get("exit_cmd")).strip():
        return None, "exit_cmd is empty — if the exit can't be a command returning 0/1, DON'T loop it (§3.5)"
    return meta, None

# --- glob matching: path-aware (* = one segment, ** = any depth), for the scope brake -------------
def _glob_re(g):
    g = re.escape(g).replace(r"\*\*", "\x00").replace(r"\*", "[^/]*").replace("\x00", ".*").replace(r"\?", "[^/]")
    return re.compile("^" + g + "$")

def in_scope(path, globs):
    res = [_glob_re(g) for g in (globs or [])]
    return any(rx.match(path) for rx in res)

def untracked_files():
    """Untracked, non-gitignored files (`ls-files --others --exclude-standard` — skips `.workflow-runtime/`
    etc. so runtime never trips the brake)."""
    s = sh(["git", "ls-files", "--others", "--exclude-standard"], cwd=str(Path.cwd()))
    return set(s.split()) if s else set()

def changed_files(start_ref, baseline_untracked):
    """Files the LOOP touched since it started = committed(start_ref..HEAD) ∪ working ∪ staged ∪ NEW-untracked.
    Untracked is essential — a `git diff` never shows a brand-new file, so without it the scope brake would
    miss an agent writing an out-of-scope `outside.txt`. But only untracked files that did NOT
    exist at loop start count: the repo may already carry unrelated untracked clutter (STATE.md, workspace
    notes) that the loop didn't create, and attributing those would false-brake. `baseline_untracked` is the
    snapshot taken at `start`."""
    out = set()
    for args in (["git", "diff", "--name-only", f"{start_ref}", "HEAD"],
                 ["git", "diff", "--name-only", "HEAD"],
                 ["git", "diff", "--name-only", "--cached"]):
        s = sh(args, cwd=str(Path.cwd()))
        if s:
            out |= set(s.split())
    out |= (untracked_files() - set(baseline_untracked or []))   # only NEW untracked
    return sorted(out)

def diff_hash():
    """Hash of the current tracked diff — identical across ticks => the worker made no change (flat diff)."""
    parts = []
    for args in (["git", "diff", "HEAD"], ["git", "diff", "--cached"]):
        try:
            r = subprocess.run(args, cwd=str(Path.cwd()), capture_output=True, text=True, timeout=30)
            parts.append(r.stdout)
        except Exception:
            parts.append("")
    return hashlib.sha256("".join(parts).encode(errors="ignore")).hexdigest()[:16]

def journal(sid, msg):
    LEASES.mkdir(parents=True, exist_ok=True)
    with open(LEASES / f"{sid}.journal", "a") as f:
        f.write(f"{now()} | {msg}\n")

# --- commands ------------------------------------------------------------------------------------
def cmd_start(a):
    sid = stream_id(a.stream)
    if not sid:
        print("[!] can't resolve stream id (no --stream and no STATE.md `**Stream:**`)"); sys.exit(1)
    live = load_lease(sid)
    if live and live.get("status") == "running":
        print(f"[!] {sid} already has a LIVE loop (iteration {live.get('iteration')}, task: {live.get('task')!r}).")
        print(f"    Finish it or `wf loop release --stream {sid}` first."); sys.exit(1)
    meta, err = parse_contract(a.contract)
    if err:
        print(f"[!] contract invalid: {err}"); sys.exit(1)
    start_ref = sh(["git", "rev-parse", "HEAD"], cwd=str(Path.cwd())) or "HEAD"
    lease = {
        "stream": sid, "status": "running", "task": meta["task"], "exit_cmd": meta["exit_cmd"],
        "max_iters": int(meta["max_iters"]), "max_unchanged": int(meta.get("max_unchanged", 2)),
        "scope": meta.get("scope") or [], "scope_slack": int(meta.get("scope_slack", 0)),
        "exit_timeout_s": int(meta.get("exit_timeout_s", 600)), "cost_note": meta.get("cost_note", ""),
        "contract_path": str(a.contract), "start_ref": start_ref,
        "baseline_untracked": sorted(untracked_files()),   # pre-existing untracked — excluded from the scope brake
        "started_at": now(), "heartbeat_at": now(), "iteration": 0, "unchanged_count": 0,
        "last_diff_hash": diff_hash(), "last_verdict": "start",
    }
    save_lease(sid, lease)
    journal(sid, f"START task={meta['task']!r} exit={meta['exit_cmd']!r} max_iters={lease['max_iters']}")
    print(f"loop[{sid}]: LEASE acquired @ {start_ref[:12]}  (max_iters={lease['max_iters']}, "
          f"max_unchanged={lease['max_unchanged']}, scope={lease['scope'] or 'ANY (⚠ no scope brake)'})")
    print(f"  task : {meta['task']}")
    print(f"  exit : {meta['exit_cmd']}")
    print(f"  → iteration 1: do the work, then `wf loop tick`. The loop opens a PR; it NEVER merges.")

def _run_exit(lease):
    """(rc, output, oracle_ok). oracle_ok=False means the exit check could NOT be evaluated — a timeout, a
    missing/non-executable binary — so the deterministic external oracle is UNAVAILABLE. That is not a
    'not done yet' verdict; the caller must fail CLOSED and STOP (§3.5 — the external check owns the stop
    decision; a broken check must never read as 'keep looping') — gate-soundness."""
    try:
        r = subprocess.run(["bash", "-c", lease["exit_cmd"]], cwd=str(Path.cwd()),
                           capture_output=True, text=True, timeout=lease.get("exit_timeout_s", 600))
        oracle_ok = r.returncode not in (126, 127)   # bash: 127 = command not found, 126 = not executable
        return r.returncode, (r.stdout + r.stderr), oracle_ok
    except subprocess.TimeoutExpired:
        return 124, "exit_cmd TIMED OUT", False
    except Exception as e:
        return 125, f"exit_cmd failed to run: {e}", False

def cmd_tick(a):
    sid = stream_id(a.stream)
    lease = load_lease(sid) if sid else None
    if not lease or lease.get("status") != "running":
        print(f"[!] no live loop for {sid or '(unknown stream)'} — `wf loop start` first."); sys.exit(1)
    lease["heartbeat_at"] = now()
    lease["iteration"] += 1
    it = lease["iteration"]

    rc, out, oracle_ok = _run_exit(lease)
    tail = "\n    ".join(out.strip().splitlines()[-4:]) if out.strip() else ""

    def stop(code, status, msg):
        lease["status"] = status
        lease["last_verdict"] = status
        save_lease(sid, lease)
        journal(sid, f"TICK {it}: STOP/{status} — {msg}")
        print(f"loop[{sid}] iter {it}: 🛑 {msg}")
        sys.exit(code)

    if not oracle_ok:
        # Fail CLOSED: the exit check couldn't run, so there is no verdict — never read that as "continue".
        stop(23, "stopped_oracle", f"ORACLE UNAVAILABLE: exit_cmd could not be evaluated (rc={rc}). "
             f"A missing/non-executable/timed-out check is NOT a verdict — fix the contract's exit_cmd."
             + (f" Tail:\n    {tail}" if tail else ""))

    if rc == 0:
        lease["status"] = "done"; lease["last_verdict"] = "done"; save_lease(sid, lease)
        journal(sid, f"TICK {it}: EXIT MET (rc=0)")
        print(f"loop[{sid}] iter {it}: ✅ EXIT MET — exit_cmd returned 0.")
        print(f"    → open a PR for the work; the loop does NOT merge (SA-only, post-CR). `wf loop release` when PR'd.")
        sys.exit(10)

    # exit not met -> guardrails
    if it >= lease["max_iters"]:
        stop(20, "stopped_budget", f"BUDGET: hit max_iters={lease['max_iters']} without exit. Last exit_cmd tail:\n    {tail}")

    cur = diff_hash()
    if cur == lease["last_diff_hash"]:
        lease["unchanged_count"] += 1
    else:
        lease["unchanged_count"] = 0
    lease["last_diff_hash"] = cur
    if lease["unchanged_count"] >= lease["max_unchanged"]:
        stop(21, "stopped_stuck", f"STUCK: {lease['unchanged_count']} iters with no diff change (max_unchanged="
                                  f"{lease['max_unchanged']}). Worker isn't making progress.")

    if lease["scope"]:
        touched = changed_files(lease["start_ref"], lease.get("baseline_untracked", []))
        outside = [f for f in touched if not in_scope(f, lease["scope"])]
        if len(outside) > lease["scope_slack"]:
            stop(22, "stopped_scope", "SCOPE BRAKE: changes outside declared scope "
                 f"(>{lease['scope_slack']} allowed): {', '.join(outside[:8])}"
                 f"{' …' if len(outside) > 8 else ''}. Stopping to ask the operator.")

    lease["last_verdict"] = "continue"
    save_lease(sid, lease)
    journal(sid, f"TICK {it}: CONTINUE (exit rc={rc}, unchanged={lease['unchanged_count']})")
    print(f"loop[{sid}] iter {it}: ↻ CONTINUE — exit not met (rc={rc}), "
          f"{lease['unchanged_count']}/{lease['max_unchanged']} unchanged, {it}/{lease['max_iters']} iters.")
    if tail:
        print(f"    exit_cmd tail:\n    {tail}")
    print(f"    → do the next iteration, then `wf loop tick`.")
    sys.exit(0)

def _stale(lease, mins=30):
    try:
        hb = datetime.datetime.strptime(lease["heartbeat_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - hb).total_seconds() > mins * 60
    except Exception:
        return False

def cmd_status(a):
    sid = stream_id(a.stream)
    if a.all or not sid:
        leases = sorted(LEASES.glob("*.json")) if LEASES.exists() else []
        if not leases:
            print("loop: no leases."); return
        for p in leases:
            try:
                l = json.loads(p.read_text())
            except Exception:
                continue
            flag = " ⚠STALE" if (l.get("status") == "running" and _stale(l)) else ""
            print(f"  {l.get('stream'):6} {l.get('status'):14} iter {l.get('iteration')}/{l.get('max_iters')} "
                  f"hb={l.get('heartbeat_at')}{flag}  task={l.get('task')!r}")
        return
    l = load_lease(sid)
    if not l:
        print(f"loop[{sid}]: no lease."); return
    flag = " ⚠STALE (heartbeat >30m — likely a dead loop; release it)" if (l.get("status") == "running" and _stale(l)) else ""
    print(json.dumps(l, indent=2)); print(f"status: {l.get('status')}{flag}")

def cmd_release(a):
    sid = stream_id(a.stream)
    l = load_lease(sid) if sid else None
    if not l:
        print(f"[!] no lease for {sid or '(unknown)'}."); sys.exit(1)
    journal(sid, f"RELEASE (was {l.get('status')} @ iter {l.get('iteration')})")
    lease_path(sid).unlink()
    print(f"loop[{sid}]: lease released (was {l.get('status')}, iter {l.get('iteration')}).")

def main():
    p = argparse.ArgumentParser(prog="loop")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--contract", required=True); s.add_argument("--stream")
    s.set_defaults(fn=cmd_start)
    t = sub.add_parser("tick"); t.add_argument("--stream"); t.set_defaults(fn=cmd_tick)
    st = sub.add_parser("status"); st.add_argument("--stream"); st.add_argument("--all", action="store_true")
    st.set_defaults(fn=cmd_status)
    r = sub.add_parser("release"); r.add_argument("--stream"); r.set_defaults(fn=cmd_release)
    a = p.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
