#!/usr/bin/env python3
"""control-plane decoupling-lint — proves the GENERIC control-plane core carries no host-project nouns.
The framework is reusable only if its core scripts/hooks/settings
mention nothing about the project that happens to host it — so this greps for project-specific tokens and
exits non-zero if any leak into the CORE zone. It is the exit ORACLE for a `wf loop` decoupling pass
AND a permanent CI gate for the framework repo.

ZONES (a flat blacklist is either noisy or gets weakened — so zone it):
  - core     : scripts/**, hooks/**, config/settings-base.json, runtime.md, loops/README.md,
               charters/_TEMPLATE.md, charters/*.template.md
               → MUST be clean. This is what ships as the framework. The charter templates live here
                 (not in `template`) because every adopter renders its apply-authority from them, so a
                 host noun leaking in must FAIL the build — and `core` is the only gated zone.
  - template : loop-template.md, charters/README.md, use-cases/**, *.example
               → placeholders/examples; project nouns tolerated as illustration (not gated here).
  - overlay  : config/streams.yaml, config/project.yaml, ownership.yaml, charters/{stream}.md
               → project-specific BY DESIGN; never gated.
  - narrative: README.md, control-plane-spec.md, DISASTER-RECOVERY.md, review-ledger.md
               → onboarding prose; reported, not gated by default.

FORBIDDEN tokens are NOT hardcoded — they are DERIVED from `config/project.yaml` (`project_name` +
`decoupling_nouns`), so this is a REUSABLE gate: it flags whatever the HOST project's own nouns are, and a
fresh repo just lists its nouns in project.yaml. NOT forbidden: the framework's own generic role vocabulary
(SA/S1/S2/S3/CR as example stream ids) — those are the framework's convention, not project nouns. The
`overlay` zone (charters) is likewise derived from `config/streams.yaml`, not frozen to today's stream names.

Usage:  decoupling-lint.py [--zone core|template|overlay|narrative|all] [--json]
  default zone = core. Exit 0 = clean; 1 = violations in the checked zone(s).
"""
import sys, re, json
from pathlib import Path

SCRIPT = Path(__file__).resolve()
import _cp_paths as cp                      # noqa: E402  (sibling module, script-dir import)

WF = cp.framework_dir(__file__)             # the framework dir — repo root (flat) or a vendored prefix

def _project():
    return cp.load_yaml(cp.config_file(WF, "project.yaml"))

#: Auto-derived `project_name` variants match only at non-alphanumeric boundaries. Plain substring
#: matching made the gate BUILD-FATAL on the framework's own shipped files for short host names:
#: `project_name: Aster` hit "DISASTER-RECOVERY.md" in charters/SA.template.md. Lookarounds are used
#: instead of `\b` because a name may legitimately begin or end with a non-word character (`@scope/pkg`),
#: where `\b` inverts its meaning and silently stops matching.
_L, _R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"
_SHORT_NAME = 5     # below this, an auto-derived noun is likely a real English word — warn, don't guess

def load_forbidden():
    """Build the forbidden-noun set from THIS project's config — a hardcoded set for one host project
    would leave every OTHER host's nouns undetected. `project_name` is auto-forbidden (case-insensitive,
    with a de-spaced variant) and **boundary-anchored**; `decoupling_nouns` are the project's explicit
    regexes, compiled RAW so a project that wants substring or fuzzy matching can still ask for it.
    Absent config → empty (the gate then only warns it has nothing to enforce).

    Trade-off, stated because it is a real limit: boundary-anchoring means `project_name: Aster` no longer
    flags `AsterClaudeEngine` (concatenation, no boundary). That is deliberate — under-detection is
    recoverable by adding the compound to `decoupling_nouns`, whereas a false positive on files the
    adopter never touched makes the whole gate un-runnable, and an un-runnable gate gets deleted."""
    p = _project()
    out = []
    name = p.get("project_name")
    if name:
        variants = {re.escape(str(name)), re.escape(str(name).replace(" ", "")), re.escape(str(name).lower())}
        shortest = min(len(str(name)), len(str(name).replace(" ", "")))
        if shortest < _SHORT_NAME:
            print(f"⚠️  decoupling-lint: project_name {name!r} is short ({shortest} chars). It is "
                  f"boundary-anchored, so it will not match inside longer words — but if it is also an "
                  f"ordinary English word it may still flag generic framework prose. Prefer an explicit "
                  f"`decoupling_nouns` list in config/project.yaml.", file=sys.stderr)
        out.append((re.compile("|".join(_L + v + _R for v in sorted(variants)), re.I),
                    f"project name ({name})"))
    for pat in (p.get("decoupling_nouns") or []):
        try:
            out.append((re.compile(pat), "project noun"))   # RAW by design — see docstring
        except re.error:
            pass
    return out

def _overlay_zone():
    """Overlay = the project-specific config + one charter per REGISTERED stream (derived from streams.yaml,
    not frozen to today's names)."""
    files = ["config/streams.yaml", "config/project.yaml", "ownership.yaml"]
    streams = cp.load_yaml(cp.config_file(WF, "streams.yaml")).get("streams", {})
    files += [f"charters/{s}.md" for s in streams]
    return files

ZONES = {
    # NB: charters/*.template.md + _TEMPLATE.md live HERE, not in `template`. They are tracked core that
    # every adopter renders its apply-authority from, so a host noun leaking in must FAIL the build — and
    # only `core` is in `gated` below. The concrete charters/<stream>.md they render into are overlay
    # (gitignored) and belong to _overlay_zone().
    "core": ["scripts/*.py", "scripts/wf", "scripts/*.sh", "hooks/*", "config/settings-base.json",
             "runtime.md", "loops/README.md", "charters/_TEMPLATE.md", "charters/*.template.md"],
    "template": ["loop-template.md", "charters/README.md", "use-cases/*", "*.example", "config/*.example*"],
    "overlay": _overlay_zone(),
    "narrative": ["README.md", "control-plane-spec.md", "DISASTER-RECOVERY.md", "SA-BOOTSTRAP.md",
                  "QUICKSTART.md", "review-ledger.md", "review-ledger.template.md"],
}
SELF = {"scripts/decoupling-lint.py",       # references config KEYS, not project nouns
        "scripts/smoke-fresh-repo.sh"}      # a meta-harness that embeds an EXAMPLE project as its fixture
FORBIDDEN = load_forbidden()

def files_for(zone):
    out = []
    for pat in ZONES[zone]:
        out += [p for p in WF.glob(pat) if p.is_file()]
    return sorted(set(out))

def scan(zone):
    violations = []
    for p in files_for(zone):
        rel = str(p.relative_to(WF))                   # framework-relative — layout-independent
        if rel in SELF:
            continue
        try:
            lines = p.read_text(errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for rx, why in FORBIDDEN:
                if rx.search(line):
                    violations.append({"file": rel, "line": i, "why": why, "text": line.strip()[:100]})
                    break
    return violations

def main():
    args = sys.argv[1:]
    zone = args[args.index("--zone") + 1] if "--zone" in args and args.index("--zone") + 1 < len(args) else "core"
    zones = list(ZONES) if zone == "all" else [zone]
    # Gate-soundness: an empty forbidden set can't protect anything — a gated run must FAIL LOUDLY, never
    # silently green (no config = no gate). This also surfaces a fresh repo that forgot to set project_name.
    if not FORBIDDEN and any(z == "core" for z in zones):
        print("❌ decoupling-lint: no forbidden nouns loaded from config/project.yaml "
              "(need project_name and/or decoupling_nouns) — cannot gate the core.", file=sys.stderr)
        sys.exit(2)
    allv = {z: scan(z) for z in zones}
    gated = [z for z in zones if z in ("core",)]        # only 'core' fails the build; others report-only
    nfail = sum(len(allv[z]) for z in gated)
    if "--json" in args:
        print(json.dumps(allv, indent=2))
    else:
        for z in zones:
            v = allv[z]
            tag = "GATED" if z in gated else "report-only"
            print(f"=== zone: {z} ({tag}) — {len(v)} hit(s) ===")
            for x in v[:40]:
                print(f"  {x['file']}:{x['line']}  [{x['why']}]  {x['text']}")
            if len(v) > 40:
                print(f"  … +{len(v) - 40} more")
        # Gate-soundness: say what was ACTUALLY checked. A `--zone template` run must not print
        # "core zone clean" — that is a green claim about a zone this invocation never scanned.
        if nfail:
            print(f"\n❌ {nfail} host-project noun(s) in the CORE zone — decouple them")
        elif gated:
            print("\n✅ core zone clean — no host-project nouns leak into the framework core")
        else:
            print(f"\n☑️  {', '.join(zones)} scanned (report-only) — the CORE zone was NOT checked "
                  f"by this run; use `--zone core` (or `--zone all`) for the gate")
    sys.exit(1 if nfail else 0)

if __name__ == "__main__":
    main()
