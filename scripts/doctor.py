#!/usr/bin/env python3
"""control-plane doctor — structured recovery report for the AI workstream control plane (spec §3.4).

READ-ONLY. Mutates nothing (no fetch, no checkout). This is the deterministic substrate of disaster
recovery: it reports the LIVE topology (`git worktree list`) against the target registry
(`config/streams.yaml`), plus per-stream git orientation, STATE headers, journals, open PRs,
stashes, and runtime state. It is also what GROUNDS control-plane-spec.md §10 — run it to corroborate
the operator-environment topology that §10 can only "report."

Usage:
  wf doctor              # human-readable report   (or: python3 scripts/doctor.py)
  wf doctor --json        # machine-readable

Drift is computed vs the LOCAL `origin/<base>` ref (as of the last fetch). Run `git fetch --all`
first if you need it fresh — doctor will not fetch for you (read-only).

`recover` = this report + the SA bootstrap prompt in DISASTER-RECOVERY.md, which reasons over the
report and regenerates each stream's restore prompt. Script is substrate; prompt is UX.
"""
import subprocess, json, sys, os, re
from pathlib import Path

def sh(args, cwd=None):
    """stdout on success (may be ""), or None if the command FAILS (non-zero exit / exception / timeout).
    Callers MUST distinguish None (unavailable) from "" (available-but-empty): a disaster-recovery tool
    must never render unreachable state (e.g. `gh` offline) as empty/clean."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                              # noqa: E402  (sibling module, script-dir import)

FRAMEWORK = cp.framework_dir(__file__)              # dir containing scripts/ — flat OR vendored
REPO_ROOT = cp.repo_root(FRAMEWORK)                 # git toplevel, not a parent-hop count


def load_registry():
    return cp.load_yaml(cp.config_file(FRAMEWORK, "streams.yaml")).get("streams", {}) or {}


def worktrees():
    """LIST of {path, branch, head} from `git worktree list --porcelain`. Matched by absolute path
    downstream — basenames can collide (multiple worktrees named the same in different parent dirs;
    e.g. review-tool clones), so keying by basename would bind a stream to the wrong checkout."""
    out = sh(["git", "worktree", "list", "--porcelain"], cwd=str(REPO_ROOT)) or ""
    res, cur = [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                res.append(cur)
            cur = {"path": line[9:]}
        elif line.startswith("HEAD "):
            cur["head"] = line[5:17]
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line.strip() == "detached":
            cur["branch"] = "(detached)"
    if cur:
        res.append(cur)
    return res


def resolve_streams(reg, wts):
    """Map each registry stream → its live worktree by EXACT expected path (<dev_root>/<name>), falling
    back to a UNIQUE basename match; >1 same-named + none-at-expected = ambiguous (never guess — basename
    collisions across parent dirs are a real bug class). The single collision-safe resolver, shared by the
    report (`build`) and the compliance gate (`compliance`) so the two can't drift apart.
    Returns [{stream, meta, worktree, expected_path, registered, ambiguous, wt}] preserving registry order."""
    dev_root = REPO_ROOT.parent
    by_path = {w["path"]: w for w in wts}
    by_base = {}
    for w in wts:
        by_base.setdefault(os.path.basename(w["path"]), []).append(w)
    out = []
    for sid, meta in reg.items():
        wtname = meta.get("worktree")
        expected = str(dev_root / wtname)
        wt, ambiguous = by_path.get(expected), False
        if not wt:
            cands = by_base.get(wtname, [])
            if len(cands) == 1:
                wt = cands[0]
            elif len(cands) > 1:
                ambiguous = True                # >1 same-named worktree, none at expected path — don't guess
        out.append({"stream": sid, "meta": meta, "worktree": wtname, "expected_path": expected,
                    "registered": bool(wt), "ambiguous": ambiguous, "wt": wt})
    return out


def drift(path, base):
    if not base:
        return None
    out = sh(["git", "rev-list", "--left-right", "--count", f"origin/{base}...HEAD"], cwd=path)
    if not out:                       # None (command failed, e.g. origin/base missing) or "" — no drift info
        return None
    parts = out.replace("\t", " ").split()
    if len(parts) != 2:
        return None
    behind, ahead = parts
    return {"ahead": int(ahead), "behind": int(behind), "base": base}


def state_active(path):
    p = Path(path) / "STATE.md"
    if not p.exists():
        return ""
    lines = p.read_text().splitlines()
    for i, l in enumerate(lines):
        if l.strip().lower().startswith("## active task"):
            for x in lines[i + 1:i + 4]:
                if x.strip().startswith("-"):
                    return x.strip("- ").strip()[:140]
    return ""


def journal_tail(path):
    p = Path(path) / "STATE.journal.md"
    if not p.exists():
        return ""
    ls = [l for l in p.read_text().splitlines() if l.strip()]
    return ls[-1] if ls else ""


def dirty_count(path):
    out = sh(["git", "status", "--porcelain"], cwd=path)
    return None if out is None else len([l for l in out.splitlines() if l])


def build():
    reg, wts = load_registry(), worktrees()
    report = {"repo_root": str(REPO_ROOT), "streams": [], "global": {}}
    matched_paths = set()
    for rs in resolve_streams(reg, wts):
        meta, wt = rs["meta"], rs["wt"]
        e = {"stream": rs["stream"], "worktree": rs["worktree"], "expected_path": rs["expected_path"],
             "expected_base": meta.get("base"), "registered": rs["registered"], "ambiguous": rs["ambiguous"]}
        if wt:
            matched_paths.add(wt["path"])
            e.update({"path": wt["path"], "branch": wt.get("branch"), "head": wt.get("head"),
                      "dirty": dirty_count(wt["path"]), "drift": drift(wt["path"], meta.get("base")),
                      "state_active": state_active(wt["path"]), "journal_tail": journal_tail(wt["path"])})
        report["streams"].append(e)
    g = report["global"]
    g["unregistered_worktrees"] = [w["path"] for w in wts if w["path"] not in matched_paths]
    prs = sh(["gh", "pr", "list", "--json", "number,title,headRefName",
              "--jq", '.[]|"#\(.number) [\(.headRefName)] \(.title)"'])
    g["open_prs"] = None if prs is None else [l for l in prs.splitlines() if l]   # None = gh unavailable
    stash = sh(["git", "stash", "list"], cwd=str(REPO_ROOT))
    g["stashes"] = None if stash is None else [l for l in stash.splitlines() if l]
    # Runtime lives in the CANONICAL main-root .workflow-runtime (shared across worktrees), resolved
    # via git-common-dir — same convention as dispatch.py, so doctor sees the real shared queue.
    main_root = cp.main_root(REPO_ROOT)
    disp, leases = main_root / ".workflow-runtime" / "dispatch", main_root / ".workflow-runtime" / "leases"
    if disp.exists():
        # An envelope is PENDING if any EXPECTED addressee has not acked (per-stream markers
        # <id>__<stream>.json). Unicast to X expects {X}; broadcast to all expects every registry
        # stream except the sender. This counts a partially-acked broadcast as still pending — a DR
        # tool must not hide unconsumed work.
        stream_ids = set(reg.keys())
        acked_by = {}
        if (disp / ".acks").exists():
            for p in (disp / ".acks").glob("*.json"):
                eid, _, st = p.stem.partition("__")
                acked_by.setdefault(eid, set()).add(st)
        pending = 0
        for f in disp.glob("*.json"):
            try:
                e = json.loads(f.read_text())
            except Exception:
                continue
            to = e.get("to")
            expected = (stream_ids - {e.get("from")}) if to in ("all", "ALL") else {to}
            if not expected <= acked_by.get(e["id"], set()):
                pending += 1
        g["pending_envelopes"] = pending
    else:
        g["pending_envelopes"] = "n/a (queue not initialized)"
    # Loop leases (§3.5): one <stream>.json per live loop. Surface iteration + STALE (heartbeat >30m on a
    # still-"running" lease = likely a dead loop that needs release) — the crash-recovery half of the contract.
    g["loop_leases"] = []
    if leases.exists():
        import datetime as _dt
        for lp in sorted(leases.glob("*.json")):
            try:
                lz = json.loads(lp.read_text())
            except Exception:
                continue
            stale = False
            if lz.get("status") == "running":
                try:
                    hb = _dt.datetime.strptime(lz["heartbeat_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
                    stale = (_dt.datetime.now(_dt.timezone.utc) - hb).total_seconds() > 1800
                except Exception:
                    pass
            g["loop_leases"].append({"stream": lz.get("stream"), "status": lz.get("status"),
                                     "iteration": lz.get("iteration"), "max_iters": lz.get("max_iters"),
                                     "heartbeat_at": lz.get("heartbeat_at"), "stale": stale,
                                     "task": lz.get("task")})
    else:
        g["loop_leases"] = None            # None = leases dir not created yet (no loop ever run)
    return report


def compliance(reg, wts):
    """Pre-operationalize GATE (spec §3.4). This is an **operator-machine** gate — it must run where the
    stream worktrees live (SA's machine), NOT on a bare CI checkout. For EVERY stream in the registry it
    verifies the stream is present AND ready; any shortfall exits non-zero:
      (0) worktree PRESENT + unambiguous — a registry stream with no worktree (or an ambiguous one) is itself
          a FAILURE: you cannot operationalize an absent stream, and silently skipping it would let the gate
          green-light a machine that has NONE of the streams). So "not registered" == FAIL here
          (unlike the recovery report, which merely notes it).
      (1) STATE.md present — no STATE = no identity, no auto-restore.
      (2) STATE `**Stream:**` id == registry key — the inbox ROUTER key (`inbox-peek.py` parses this exact
          token). A mismatch silently misroutes every dispatch to/from the stream — STATE says one id, the
          registry another, so the probe stream's inbox goes to the void (a real incident this gate prevents).
      (3) live `.claude/settings.json` == `gen-config` output — merge-policy (SA-only) not drifted. Uses
          gen-config itself as the ORACLE (`--dry-run --worktree X` → `[ok]`), so there is ZERO settings-logic
          duplicated here to drift.
    READ-ONLY. Returns per-stream verdicts (each has `ok`); the caller exits non-zero if any `ok` is false."""
    gencfg = SCRIPT.parent / "gen-config.py"
    rows = []
    for rs in resolve_streams(reg, wts):
        sid = rs["stream"]
        if rs["ambiguous"]:
            rows.append({"stream": sid, "ok": False,
                         "reason": "ambiguous worktree (>1 same-named, none at expected path — cannot resolve)"}); continue
        if not rs["registered"]:
            rows.append({"stream": sid, "ok": False,
                         "reason": f"no worktree at {rs['expected_path']} (cannot operationalize an absent stream)"}); continue
        path = rs["wt"]["path"]
        st = Path(path) / "STATE.md"
        state_present = st.exists()
        # (2) canonical inbox-peek regex — MUST match hooks/inbox-peek.py::stream_id() exactly.
        declared = None
        if state_present:
            for line in st.read_text().splitlines():
                m = re.search(r"\*\*Stream:\*\*\s*([A-Za-z0-9/_-]+)", line)
                if m:
                    declared = m.group(1).strip().rstrip("."); break
        id_ok = state_present and declared == sid
        # (3) gen-config is the oracle — no settings logic duplicated in doctor.
        out = sh(["python3", str(gencfg), "--dry-run", "--worktree", rs["worktree"]], cwd=str(REPO_ROOT))
        if out is None:
            settings_ok, settings_reason = False, "gen-config failed (unavailable)"
        elif "[ok]" in out:
            settings_ok, settings_reason = True, None
        elif "[diff]" in out:
            settings_ok, settings_reason = False, "differs from gen-config (run `wf gen-config`)"
        else:
            settings_ok, settings_reason = False, (out.strip().splitlines() or ["unexpected gen-config output"])[0][:80]
        rows.append({"stream": sid,
                     "ok": bool(state_present and id_ok and settings_ok),
                     "state_present": state_present, "declared_id": declared, "id_ok": id_ok,
                     "settings_ok": settings_ok, "settings_reason": settings_reason})
    return rows


def human_compliance(rows):
    o = ["=== doctor --compliance — operator-machine pre-operationalize gate (read-only) ===",
         "EVERY registry stream must be present + ready:  worktree present · STATE present · "
         "STATE-id == registry key · settings == gen-config", ""]
    n_fail = 0
    for r in rows:
        if r["ok"]:
            o.append(f"  [PASS] {r['stream']:5}")
            continue
        n_fail += 1
        if "reason" in r:                       # resolution failure (absent / ambiguous worktree)
            o.append(f"  [FAIL] {r['stream']:5} — {r['reason']}")
            continue
        bad = []
        if not r["state_present"]:
            bad.append("no STATE.md")
        elif not r["id_ok"]:
            bad.append(f"STATE-id '{r['declared_id']}' != registry '{r['stream']}' (dispatch misroutes!)")
        if not r["settings_ok"]:
            bad.append(f"settings: {r['settings_reason']}")
        o.append(f"  [FAIL] {r['stream']:5} — " + "; ".join(bad))
    o += ["", (f"❌ {n_fail} of {len(rows)} stream(s) FAIL — not operationalize-ready" if n_fail
               else f"✅ all {len(rows)} registered streams present + compliant")]
    return "\n".join(o), n_fail


def human(r):
    o = ["=== doctor — recovery report ===", f"repo root: {r['repo_root']}", "",
         "STREAMS (target registry vs live git worktrees):"]
    for s in r["streams"]:
        if s.get("ambiguous"):
            o.append(f"  [?] {s['stream']:5} {s['worktree']:24} AMBIGUOUS — multiple worktrees named "
                     f"'{s['worktree']}', none at expected path {s['expected_path']} (cannot resolve safely)")
            continue
        if not s["registered"]:
            o.append(f"  [!] {s['stream']:5} {s['worktree']:24} NOT REGISTERED (expected {s['expected_path']}, base {s['expected_base']})")
            continue
        d = s.get("drift")
        dtxt = f"^{d['ahead']} v{d['behind']} vs origin/{d['base']}" if d else "drift n/a (fetch?)"
        dc = s.get("dirty")
        dirty = "dirty n/a" if dc is None else (f"{dc} dirty" if dc else "clean")
        o.append(f"  [ok] {s['stream']:5} {s['worktree']:24} [{s['branch']}] @ {s['head']}  {dtxt}  {dirty}")
        if s.get("state_active"):
            o.append(f"          task: {s['state_active']}")
        if s.get("journal_tail"):
            o.append(f"          last: {s['journal_tail']}")
    g = r["global"]
    if g["unregistered_worktrees"]:
        o.append("\nUNREGISTERED worktrees (in git, not matched to a registry stream):")
        o += [f"  {p}" for p in g["unregistered_worktrees"]]
    if g["open_prs"] is None:
        o.append("\nOPEN PRs: [!] UNAVAILABLE (gh error / offline) — NOT 'none'")
    else:
        o.append(f"\nOPEN PRs ({len(g['open_prs'])}):")
        o += [f"  {p}" for p in g["open_prs"]] or ["  (none)"]
    if g["stashes"] is None:
        o.append("\nSTASHES: [!] UNAVAILABLE (git error)")
    elif g["stashes"]:
        o.append(f"\nSTASHES ({len(g['stashes'])}):")
        o += [f"  {s}" for s in g["stashes"]]
    ll = g["loop_leases"]
    lease_txt = "n/a (none run)" if ll is None else (f"{len(ll)}" if ll else "0")
    o.append(f"\nRUNTIME: pending envelopes={g['pending_envelopes']}, loop leases={lease_txt}")
    for lz in (ll or []):
        flag = " 🔴 STALE (heartbeat >30m — release it)" if lz.get("stale") else ""
        o.append(f"  loop {lz.get('stream'):6} {lz.get('status'):14} iter {lz.get('iteration')}/{lz.get('max_iters')}"
                 f"  hb={lz.get('heartbeat_at')}{flag}")
    o.append("\n(read-only; drift is as-of-last-fetch. `recover` = this + the SA bootstrap "
             "prompt in DISASTER-RECOVERY.md)")
    return "\n".join(o)


if __name__ == "__main__":
    if "--compliance" in sys.argv:
        # GATE mode: local + offline (no gh/network), OPERATOR-MACHINE (must run where the worktrees live).
        # Exits non-zero if ANY registry stream is not present+ready. Does NOT run the full recovery report.
        rows = compliance(load_registry(), worktrees())
        if "--json" in sys.argv:
            print(json.dumps({"compliance": rows}, indent=2))
        else:
            text, _ = human_compliance(rows)
            print(text)
        sys.exit(1 if any(not r.get("ok") for r in rows) else 0)
    r = build()
    print(json.dumps(r, indent=2) if "--json" in sys.argv else human(r))
