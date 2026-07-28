#!/usr/bin/env python3
"""control-plane pre-push — READ-ONLY guard against the RECURRING review-finding classes (review-ledger.md).

The framework's §1.1 #5: recurring failure modes graduate from prose → a mechanized gate. This greps the
branch diff for the classes that (a) recur and (b) a grep can catch, then prints the human-eye reminders
for the classes it can't. It is ADVISORY (warns, exits 0) — a guard, not a blocker — so it never gets in
the way of a legitimate exception; you decide.

Run it before pushing:  wf pre-push  [--base <ref>]
Default base = origin/<this stream's registry base> (resolved from the worktree's STATE.md id → streams.yaml),
so it works for streams that fork off a non-main integration branch; it falls back to origin/main only when
the stream/base can't be resolved. Override any time with --base.
"""
import subprocess, sys, re, os
from pathlib import Path

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                              # noqa: E402  (sibling module, script-dir import)


def sh(args, cwd=None):
    """(stdout, ok) — ok=False on non-zero exit / exception / timeout, so a callers can distinguish
    'no output' from 'command FAILED'. Critical here: a failed `git diff` must NOT read as an empty
    (== clean) tree — that would make an unresolvable base a silent false-clean."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20)
        return r.stdout, r.returncode == 0
    except Exception:
        return "", False


ROOT = cp.main_root(SCRIPT.parent)
FRAMEWORK = cp.framework_in(ROOT)
# Repo-relative paths of the files that legitimately NAME the patterns they'd otherwise trip on. Built
# from the resolved framework dir so they stay correct in both layouts (flat repo vs vendored prefix).
try:
    _fw = FRAMEWORK.relative_to(ROOT).as_posix() if FRAMEWORK != ROOT else ""
except ValueError:                      # framework outside the repo root (exotic install) — no prefix
    _fw = ""
_p = (lambda rel: f"{_fw}/{rel}" if _fw else rel)
SELF = {_p("review-ledger.md"), _p("review-ledger.template.md"), _p("scripts/pre-push-check.py")}


def changed_files(base_ref):
    """(files, base_ok, note). base_ok=False means the base ref / committed-diff couldn't be computed (e.g.
    the integration base isn't fetched locally, or a bad --base) — the caller MUST warn loudly, because an
    empty list would otherwise read as a clean tree. Working-tree + staged diffs don't depend on the base,
    so they're always included (still real signal even when the base leg is unavailable)."""
    mb_out, mb_ok = sh(["git", "merge-base", "HEAD", base_ref], cwd=str(ROOT))
    base = mb_out.strip()
    committed, base_ok, note = [], True, ""
    if mb_ok and base:
        diff_out, d_ok = sh(["git", "diff", "--name-only", base, "HEAD"], cwd=str(ROOT))
        if d_ok:
            committed = diff_out.split()
        else:
            base_ok, note = False, f"`git diff {base[:12]}..HEAD` failed"
    else:
        base_ok, note = False, f"cannot resolve base ref '{base_ref}' — fetched? (`git fetch origin`)"
    working, _ = sh(["git", "diff", "--name-only", "HEAD"], cwd=str(ROOT))
    staged, _ = sh(["git", "diff", "--name-only", "--cached"], cwd=str(ROOT))
    files = sorted(set(committed) | set(working.split()) | set(staged.split()))
    return files, base_ok, note


def read(rel):
    p = ROOT / rel
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""


def default_base():
    """Diff base for THIS worktree's stream = origin/<its registry base>. Streams may fork off DIFFERENT bases
    (some off main, some off a shared integration branch), so a hard-coded origin/main makes the guard diff the
    whole inherited integration delta for the integration streams — noisy on exactly the streams that use it
    most. Resolve the stream id from the worktree's STATE.md (same token inbox-peek/doctor use) → its `base`
    in the registry. Fall back to origin/main only when unresolvable.
    Returns (base_ref, human_source)."""
    sid = None
    try:
        for line in (Path.cwd() / "STATE.md").read_text().splitlines():
            m = re.search(r"\*\*Stream:\*\*\s*([A-Za-z0-9/_-]+)", line)
            if m:
                sid = m.group(1).strip().rstrip("."); break
    except Exception:
        pass
    if sid:
        reg = cp.load_yaml(cp.config_file(FRAMEWORK, "streams.yaml")).get("streams", {})
        b = (reg.get(sid) or {}).get("base")
        if b:
            return f"origin/{b}", f"registry: {sid} → {b}"
    return "origin/main", f"fallback origin/main (stream/base unresolved{f'; STATE id={sid}' if sid else '; no STATE id'})"


def main():
    args = sys.argv[1:]
    if "--base" in args and args.index("--base") + 1 < len(args):
        base, base_source = args[args.index("--base") + 1], "explicit --base"
    else:
        base, base_source = default_base()
    all_files, base_ok, note = changed_files(base)
    files = [f for f in all_files if f not in SELF]
    print("=" * 84)
    print("PRE-PUSH GUARD — recurring review-finding classes (review-ledger.md)")
    print(f"  {len(files)} changed file(s) vs merge-base({base})   [base: {base_source}]")
    if not base_ok:
        print("-" * 84)
        print(f"⚠️  BASE UNRESOLVED — {note}")
        print("    The committed-diff leg could NOT be computed, so this run inspects only your")
        print("    working-tree + staged changes. A '0 changed files / no hits' result here is NOT a")
        print("    clean bill of health — fetch the base (`git fetch origin`) or pass a valid --base, re-run.")
    print("=" * 84)
    warnings = 0

    # 1. worktree/path resolution by basename (near worktree/registry logic)
    for f in files:
        if not f.endswith(".py"):
            continue
        t = read(f)
        if re.search(r"basename\(", t) and re.search(r"worktree|registry|streams\.yaml|git worktree", t, re.I):
            warnings += 1
            print(f"\n⚠️  [worktree-resolution] {f}")
            print("    contains basename() near worktree/registry logic — derive the CANONICAL path")
            print("    (<dev_root>/<name> or git-common-dir), don't basename-match `git worktree list`.")

    # 2. operator-machine path hard-coded as universal
    pat = re.compile(r"/Users/[a-z0-9_]+/|-Users-[a-z0-9]+-(?:Developer|Documents)-")
    for f in files:
        hits = [ln for ln in read(f).splitlines()
                if pat.search(ln) and "<" not in ln.split("Users")[0][-3:]]  # crude: skip obvious <placeholder>
        if hits:
            warnings += 1
            print(f"\n⚠️  [operator-path-hardcoding] {f}  ({len(hits)} line(s))")
            print(f"    e.g. {hits[0].strip()[:90]}")
            print("    if presented as universal, use a PATTERN + 'one observed example' (not a machine path).")

    if warnings == 0:
        print("\n✅ no mechanizable recurring-class hits in the diff.")

    print("\n" + "-" * 84)
    print("👁  HUMAN-EYE (no grep catches these — verify before you push):")
    for line in [
        "parallel-inconsistency — fixed a claim/status/value? grep the SAME statement in README ↔ spec ↔ tables ↔ help-text ↔ siblings",
        "name-your-tree — every code/repo-state claim cited at file:line on the RIGHT tree (committed vs working; main vs integration)",
        "status/date overclaim — does 'validated/done' evidence cover the CURRENT documented flow?",
        "project-specific classes — see this project's review-ledger.md for any recurring gotchas",
        "stacked-PR order — retarget upper PRs before merging the stack-parent",
        "sign-off — PR/issue/CR comment signed — [<stream>/<role>]",
    ]:
        print(f"    ☐ {line}")
    print()
    sys.exit(0)   # advisory — never blocks


if __name__ == "__main__":
    main()
