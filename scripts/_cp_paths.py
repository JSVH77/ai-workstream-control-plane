#!/usr/bin/env python3
"""Layout-agnostic path resolution for the control-plane tools (the E2 extraction's layout fix).

WHY: the framework can be installed in TWO shapes and nothing may hardcode either one —
  (A) **flat / standalone** — the framework IS the repo:      <repo>/scripts/ · <repo>/config/
  (B) **vendored** — consumed via `git subtree --prefix=X`:   <repo>/X/scripts/ · <repo>/X/config/
The pre-extraction code assumed (B) with X=`workflow` (`SCRIPT.parents[2]` as the repo root, config at
`<root>/workflow/config/...`), which breaks the moment the framework is its own repo. The honest fix is to
stop counting parent hops and resolve by STRUCTURE instead:

  FRAMEWORK  = the directory that CONTAINS `scripts/` — i.e. `SCRIPT.parents[1]`. True in BOTH shapes,
               because the framework's own internal layout (`scripts/`, `config/`, `hooks/`) never changes;
               only where that directory SITS in the repo does.
  REPO_ROOT  = `git rev-parse --show-toplevel` from the framework dir (NOT a parent-hop count).
  MAIN_ROOT  = the primary worktree = parent of `--git-common-dir`. Deliberately distinct from REPO_ROOT:
               a tool invoked directly from a sibling worktree must still resolve the SHARED main-root
               runtime/config, not the checkout it happens to sit in.

`CP_FRAMEWORK_DIR` overrides the framework dir for exotic installs. Every helper degrades to a sane local
answer rather than raising — but callers that need a CONFIG file still get a real error from the read, so a
missing overlay never silently reads as "empty/clean" (gate-soundness).
"""
import os
import subprocess
from pathlib import Path

MARKER = Path("scripts") / "doctor.py"      # identifies a framework dir in either shape


def _sh(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def framework_dir(script_file):
    """The framework dir for the RUNNING script = the dir containing its `scripts/` folder.
    `script_file` is the caller's `__file__`."""
    env = os.environ.get("CP_FRAMEWORK_DIR")
    if env and (Path(env) / MARKER).exists():
        return Path(env).resolve()
    return Path(script_file).resolve().parents[1]


def framework_in(root):
    """The framework dir UNDER an arbitrary repo root — for tools that must read the MAIN worktree's
    config rather than their own checkout's. Handles both shapes: the root itself (flat), or a single
    subdirectory carrying the marker (vendored under any prefix, not just `workflow/`).
    Falls back to `root` so callers get a path whose failed read is loud, not a silent empty."""
    root = Path(root)
    env = os.environ.get("CP_FRAMEWORK_DIR")
    if env and (Path(env) / MARKER).exists():
        return Path(env).resolve()
    if (root / MARKER).exists():
        return root
    try:
        for child in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if (child / MARKER).exists():
                return child
    except Exception:
        pass
    return root


def repo_root(framework):
    """The git repo root containing the framework (`--show-toplevel`), or the framework dir if the
    framework isn't inside a git repo (a bare copy — still usable for config reads)."""
    out = _sh(["git", "rev-parse", "--show-toplevel"], cwd=str(framework))
    return Path(out).resolve() if out else Path(framework)


def main_root(start):
    """The PRIMARY worktree root = parent of the shared git dir (`--git-common-dir`). This is the canonical
    location of the shared `.workflow-runtime/` queue + leases, so every worktree agrees on one store."""
    start = Path(start)
    common = _sh(["git", "rev-parse", "--git-common-dir"], cwd=str(start))
    if not common:
        return start
    p = Path(common)
    if not p.is_absolute():
        p = (start / p).resolve()
    return p.parent


def config_file(framework, name):
    """Path to a config file inside the framework (`<framework>/config/<name>`)."""
    return Path(framework) / "config" / name


def load_yaml(path):
    """Parsed YAML mapping, or {} if unreadable/absent. Callers that GATE on the contents must treat {}
    as 'could not load' and fail loudly — never as 'nothing to enforce'."""
    try:
        import yaml
        return yaml.safe_load(Path(path).read_text()) or {}
    except Exception:
        return {}
