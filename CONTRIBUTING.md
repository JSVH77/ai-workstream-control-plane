# Contributing

The framework is small on purpose: bash hooks, Python scripts on the standard library plus PyYAML, and
Markdown. Keep it that way.

**Before a pull request**

- `shellcheck -S warning init.sh hooks/*.sh scripts/*.sh scripts/wf` — clean.
- `python3 -W error -m py_compile scripts/*.py hooks/*.py` — clean.
- `python3 scripts/decoupling-lint.py --zone core` — the core carries no host-project nouns.
- `bash scripts/smoke-fresh-repo.sh` — a blank repo stands up the substrate in both layouts.

These four run in CI (`.github/workflows/ci.yml`); a PR that fails them is not reviewed.

**Rules of the house**

- Project nouns stay in the overlay (`config/*.yaml`, `ownership.yaml`, `charters/<stream>.md`), never in
  `scripts/`, `hooks/` or `config/settings-base.json`. The decoupling lint enforces it.
- Runtime exhaust (`.workflow-runtime/`, `STATE.md`, transcript backups) is never committed.
- A gate must fail loudly when it cannot evaluate (`doctor --compliance` on an empty registry, a loop whose
  `exit_cmd` cannot run). "Nothing to check" is a failure, not a pass.
- `control-plane-spec.md` §10 is the single place that says what is live and what is design. Do not restate
  status elsewhere.
- Every PR body says how it was verified.

**Licence**

By contributing you agree that your contribution is licensed under the MIT licence in `LICENSE`.
