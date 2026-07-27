#!/usr/bin/env python3
"""control-plane mem-hygiene — READ-ONLY memory-hygiene detector for the shared vendor memory (control-plane §8).

Companion to `doctor` (worktree/git topology). Audits the vendor auto-memory.

MODEL (corrected 2026-07-24, empirical): vendor memory is **base-project-SHARED, NOT per-worktree** — every
git worktree of the repo reads & writes the SAME **MAIN** bucket (`~/.claude/projects/<main-root-slug>/memory/`).
The look-alike per-worktree buckets exist on disk but are **never loaded — dead weight (GC candidates)**.
Only `STATE.md` is per-worktree. So this tool:
  1. audits the ONE **MAIN** bucket (the only store that loads): cap%, ORPHANS (file/no-pointer),
     DANGLERS (pointer/no-file), ARCHIVE cold-tier present;
  2. checks **STATE-REF integrity** — for EACH worktree's `STATE.md`, do the memories it names exist in the
     MAIN bucket? (STATE is per-worktree but memory is shared, so a STATE can name a memory MAIN lacks —
     the "can't recall on restart" gap);
  3. lists the **DEAD per-worktree buckets** (never loaded) as GC candidates;
  4. proposes a routing target for MAIN orphans (archive / git-Tier-A / review).

MUTATES NOTHING — detects + proposes; any move/GC is a separate reviewed step.

Usage:  wf mem-hygiene [--json] [--routing]   |   python3 scripts/mem-hygiene.py [...]
"""
import json, sys, os, re, glob, subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                              # noqa: E402  (sibling module, script-dir import)

# The base-project MAIN worktree = parent of the shared **git-common-dir** — robust from ANY worktree
# (mirrors `wf`). Deliberately NOT a parent-hop from the script: that yields the worktree the SCRIPT lives
# in, so a DIRECT `python3 …/mem-hygiene.py` run from a sibling checkout would resolve that worktree's
# *dead* bucket instead of the shared MAIN one. git-common-dir → the primary worktree = the base project
# whose bucket the vendor actually loads for every stream.
MAIN_ROOT = cp.main_root(SCRIPT.parent)
# Config comes from the MAIN worktree's framework dir (not this checkout's) for the same reason.
MAIN_FRAMEWORK = cp.framework_in(MAIN_ROOT)
PROJECTS = Path.home() / ".claude" / "projects"
CAP_BYTES = int(24.4 * 1024)                  # ~24.4 KB MEMORY.md load cap (over -> silent truncation)
WARN_FRAC = 0.80
SKIP = {"MEMORY.md", "ARCHIVE.md"}


def load_registry():
    return cp.load_yaml(cp.config_file(MAIN_FRAMEWORK, "streams.yaml")).get("streams", {}) or {}


def bucket_dir(worktree_abspath):
    return PROJECTS / str(worktree_abspath).replace("/", "-") / "memory"


def stream_paths():
    """{stream_id: canonical abs worktree path} = <dev_root>/<registry worktree-name> (mirrors doctor.py;
    NOT basename-matched against `git worktree list`, which collides across scratch worktrees)."""
    reg = load_registry()
    dev_root = MAIN_ROOT.parent
    return {sid: str(dev_root / v["worktree"]) for sid, v in reg.items() if v.get("worktree")}


MAIN_BUCKET = bucket_dir(str(MAIN_ROOT))       # the ONE operative store (base-project = main root)

def load_affinity():
    """stream_id -> filename regex, from config/project.yaml `memory_affinity` (an OPTIONAL project-local
    routing heuristic for MAIN-bucket orphans). Empty if absent — the framework core carries no project
    nouns; a fresh project defines its own (or none, and orphans just route to REVIEW)."""
    m = cp.load_yaml(cp.config_file(MAIN_FRAMEWORK, "project.yaml")).get("memory_affinity") or {}
    return list(m.items())

AFFINITY = load_affinity()

def _historical():
    """Filename patterns that mark a memory as a point-in-time SNAPSHOT (a status/kickoff/wrap-up note)
    rather than durable knowledge — the archive-tier candidates. Generic by default (dated + session-phase
    shapes); a project can extend/replace the list via `historical_patterns` in project.yaml."""
    pats = cp.load_yaml(cp.config_file(MAIN_FRAMEWORK, "project.yaml")).get("historical_patterns")
    default = [r"_kickoff_", r"pickup_", r"_wrapup", r"compaction_recovery",
               r"current_state_\d{4}", r"_status_\d{4}_\d{2}", r"_\d{4}_\d{2}_\d{2}$"]
    try:
        return re.compile("|".join(pats or default), re.I)
    except re.error:
        return re.compile("|".join(default), re.I)

HISTORICAL = _historical()


def affinity(f):
    s = f.lower()
    for tag, pat in AFFINITY:
        if re.search(pat, s):
            return tag
    return "?"


def index_refs(text):
    return {os.path.basename(m) for m in re.findall(r"\(([A-Za-z0-9_./-]+\.md)\)", text)}


def state_mem_tokens(text):
    return set(re.findall(r"\b((?:project|feedback|reference)_[a-z0-9_]+)\b", text))


def audit_main():
    m = MAIN_BUCKET
    r = {"path": str(m), "exists": m.is_dir()}
    if not m.is_dir():
        return r
    idx = (m / "MEMORY.md").read_text() if (m / "MEMORY.md").exists() else ""
    arc = (m / "ARCHIVE.md").read_text() if (m / "ARCHIVE.md").exists() else ""
    combined = idx + "\n" + arc
    files = [os.path.basename(f) for f in glob.glob(str(m / "*.md"))
             if os.path.basename(f) not in SKIP and not os.path.basename(f).startswith("_MEMORY_full")]
    on_disk = set(files) | SKIP
    r["files"] = len(files)
    r["memory_md_bytes"] = (m / "MEMORY.md").stat().st_size if (m / "MEMORY.md").exists() else 0
    r["cap_pct"] = round(100 * r["memory_md_bytes"] / CAP_BYTES, 1)
    r["archive_present"] = (m / "ARCHIVE.md").exists()
    r["orphans"] = sorted(f for f in files if f not in combined)
    r["danglers"] = sorted(ref for ref in index_refs(combined) if ref not in on_disk)
    r["on_disk"] = on_disk
    return r


def state_ref_integrity(main_on_disk):
    """For each worktree's STATE.md, memories it names that are NOT in the MAIN (loaded) bucket."""
    out = []
    for sid, wt in sorted(stream_paths().items()):
        st = Path(wt) / "STATE.md"
        if not st.exists():
            out.append({"stream": sid, "state_md": False, "missing": []}); continue
        missing = sorted(t + ".md" for t in state_mem_tokens(st.read_text()) if t + ".md" not in main_on_disk)
        out.append({"stream": sid, "state_md": True, "missing": missing})
    return out


def dead_buckets():
    """Per-worktree (non-main) buckets — exist on disk but are never loaded. GC candidates."""
    out = []
    for sid, wt in sorted(stream_paths().items()):
        b = bucket_dir(wt)
        if b == MAIN_BUCKET or not b.is_dir():
            continue
        n = len([f for f in glob.glob(str(b / "*.md"))
                 if os.path.basename(f) not in SKIP and not os.path.basename(f).startswith("_MEMORY_full")])
        out.append({"stream": sid, "path": str(b), "files": n})
    return out


def route(f):
    if HISTORICAL.search(f):
        return "ARCHIVE? (historical)"
    a = affinity(f)
    if a == "SHARED":
        return "REVIEW: promote to git Tier A? (shared/durable)"
    if a == "?":
        return "REVIEW (unclassified — human eye)"
    return "KEEP (index it)"


def human(main, srefs, dead, show_routing):
    print("=" * 90)
    print("MEMORY-HYGIENE — read-only. Model: ONE shared MAIN bucket loads for every worktree (§8, 2026-07-24).")
    print(f"  cap = {CAP_BYTES}B (~24.4KB); warn >= {int(WARN_FRAC*100)}%")
    print("=" * 90)
    print(f"\n=== MAIN bucket (the only store that loads) ===\n  {main['path']}")
    if not main.get("exists"):
        print("  ⚠️ MAIN bucket not found!")
    else:
        cap = main["cap_pct"]
        flag = " ⚠️OVER-CAP" if cap >= 100 else (" ⚠️near-cap" if cap >= WARN_FRAC * 100 else "")
        arc = "" if main["archive_present"] else "  ⚠️no ARCHIVE.md (no cold tier)"
        print(f"  files={main['files']}  MEMORY.md={main['memory_md_bytes']}B ({cap}%){flag}{arc}")
        if main["orphans"]:
            print(f"  ORPHANS ({len(main['orphans'])}): " + ", ".join(main["orphans"][:12]) + (" …" if len(main["orphans"]) > 12 else ""))
        if main["danglers"]:
            print(f"  DANGLERS ({len(main['danglers'])}): " + ", ".join(main["danglers"][:12]))
        if not (main["orphans"] or main["danglers"] or flag or arc):
            print("  ✅ clean")
    print("\n=== STATE-REF integrity — each worktree's STATE.md vs the MAIN bucket ===")
    for s in srefs:
        if not s["state_md"]:
            print(f"  {s['stream']:5} (no STATE.md)")
        elif s["missing"]:
            print(f"  {s['stream']:5} 🔴 STATE-REF-MISSING ({len(s['missing'])}): " + ", ".join(s["missing"]) +
                  "   (STATE names these; not in MAIN — unrecallable on restart)")
        else:
            print(f"  {s['stream']:5} ✅ all refs resolve in MAIN")
    print("\n=== DEAD per-worktree buckets (never loaded — GC candidates) ===")
    if not dead:
        print("  (none)")
    for d in dead:
        print(f"  {d['stream']:5} {d['files']:>4} files   {d['path']}   ← dead; safe to GC (back up first)")
    if show_routing and main.get("orphans"):
        print("\n=== PROPOSED ROUTING for MAIN orphans (REVIEW before acting) ===")
        for f in main["orphans"]:
            print(f"  {route(f):<42} {f}")
    print()


def main():
    args = sys.argv[1:]
    m = audit_main()
    srefs = state_ref_integrity(m.get("on_disk", set()))
    dead = dead_buckets()
    if "--json" in args:
        m.pop("on_disk", None)
        print(json.dumps({"main": m, "state_ref": srefs, "dead_buckets": dead}, indent=2))
    else:
        human(m, srefs, dead, "--routing" in args)


if __name__ == "__main__":
    main()
