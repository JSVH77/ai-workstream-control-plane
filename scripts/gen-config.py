#!/usr/bin/env python3
"""control-plane gen-config — generate each worktree's .claude/settings.json from the registry (spec §3.7).

Makes streams.yaml LOAD-BEARING instead of documentation: the per-worktree settings are no longer
hand-kept in sync — they are regenerated from a shared floor + per-stream policy.

  generic floor = config/settings-base.json  (allow incl Bash(*), GENERIC safety deny, hooks with a
                  {{HOOK_NAMESPACE}} placeholder, plugins) — project-agnostic, ships with the framework.
  project overlay = config/project.yaml  (hook_namespace -> substituted into the floor; protected_paths
                  + extra_denies -> appended to deny). This is the floor/overlay split.
  per-stream    = streams.yaml `can_merge`: false -> add gh-pr-merge AND the GitHub MCP merge tool to that
                  worktree's deny (SA-only merge, enforced on BOTH surfaces — closes the MCP gap).

Model is a runtime `/model` concern, not a settings.json key — not written here.
Does NOT touch .claude/settings.local.json (the personal per-worktree override).

Usage:
  gen-config.py --dry-run                     # show what would change per worktree (default: all)
  gen-config.py                               # write each registered worktree's .claude/settings.json
  gen-config.py --worktree <worktree-name> [--dry-run]

Only writes worktrees that are actually registered (matched by expected path <dev-root>/<name>).
"""
import json, subprocess, argparse, copy
from pathlib import Path

MERGE_DENY = ["Bash(gh pr merge:*)", "mcp__github__merge_pull_request"]

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
DEV_ROOT = REPO_ROOT.parent

def registered_paths():
    out = sh(["git", "worktree", "list", "--porcelain"], cwd=str(REPO_ROOT)) or ""
    return {line[9:] for line in out.splitlines() if line.startswith("worktree ")}

def gen_settings(base, can_merge, project_denies):
    s = copy.deepcopy(base)
    deny = [d for d in s["permissions"]["deny"] if d not in MERGE_DENY]    # normalize merge-deny
    for d in project_denies:                                              # project overlay (dedup, order-stable)
        if d not in deny:
            deny.append(d)
    allow = list(s["permissions"].get("allow", []))
    if not can_merge:
        deny += MERGE_DENY
        # ...and drop the same rules from `allow`. The floor allows `gh pr merge` (SA needs it), so without
        # this a merge-denied stream carried the rule verbatim in BOTH lists. Deny wins in Claude Code, so
        # it was never exploitable — this is an auditability fix: a reader should not find the literal rule
        # on both sides.
        # LIMIT, stated so nobody reads more into this than it does: the strip is EXACT-MATCH, and the
        # floor's allow list ends with a blanket `Bash(*)`. The generated file therefore still permits
        # `gh pr merge` BY PATTERN while denying it literally. That is the intended posture (deny is the
        # enforcement surface, allow is the convenience surface) — but it means "audit by reading `allow`"
        # is not achievable here, and only `deny` is load-bearing for the SA-only-merge policy.
        allow = [a for a in allow if a not in MERGE_DENY]
    s["permissions"]["allow"] = allow
    s["permissions"]["deny"] = deny
    return s

def load_project():
    """Project overlay (config/project.yaml): hook_namespace + the deny overlay (protected_paths + extra_denies)."""
    p = cp.load_yaml(cp.config_file(FRAMEWORK, "project.yaml"))
    ns = p.get("hook_namespace")
    if not ns:
        raise SystemExit("gen-config: config/project.yaml missing hook_namespace")
    denies = [f"Bash(rm -rf {x})" for x in (p.get("protected_paths") or [])] + list(p.get("extra_denies") or [])
    return ns, denies

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--worktree")
    a = ap.parse_args()
    ns, project_denies = load_project()
    # Substitute the {{HOOK_NAMESPACE}} placeholder in the generic floor before parsing (project overlay).
    base = json.loads(cp.config_file(FRAMEWORK, "settings-base.json").read_text().replace("{{HOOK_NAMESPACE}}", ns))
    reg = cp.load_yaml(cp.config_file(FRAMEWORK, "streams.yaml")).get("streams", {})
    paths = registered_paths()
    for sid, meta in reg.items():
        wt = meta.get("worktree")
        if a.worktree and wt != a.worktree:
            continue
        expected = str(DEV_ROOT / wt)
        if expected not in paths:
            print(f"[skip]  {sid:5} {wt:24} — not registered at {expected}")
            continue
        target = Path(expected) / ".claude" / "settings.json"
        newtext = json.dumps(gen_settings(base, bool(meta.get("can_merge")), project_denies), indent=2) + "\n"
        cur = target.read_text() if target.exists() else None
        policy = "MERGE-ALLOW" if meta.get("can_merge") else "merge-deny"
        if cur == newtext:
            print(f"[ok]    {sid:5} {wt:24} — up to date ({policy})")
        elif a.dry_run:
            print(f"[diff]  {sid:5} {wt:24} — WOULD write ({policy}, {'new file' if cur is None else 'differs'})")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(newtext)
            print(f"[write] {sid:5} {wt:24} — wrote .claude/settings.json ({policy})")

if __name__ == "__main__":
    main()
