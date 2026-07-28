# Use / test cases

Reusable **operator playbooks** for the control plane — each one is a scenario ("I want to do X"), the
**sequence of steps**, and the **verification** that proves it worked. They double as **test cases**: run
one end-to-end and you've validated that slice of the workflow with the real sessions.

Each case names the **actor** for every step — **Operator** (you), **SA** (the orchestrator session you
drive), or **(auto)** (something the framework does for you, e.g. a hook).

| ID | Scenario | Provenance |
|---|---|---|
| [UC-00](UC-00-bootstrap-fresh-repo.md) | Bootstrap the control plane in a **fresh repo** (day-0 stand-up) — see also [`../QUICKSTART.md`](../QUICKSTART.md) | its exit bar (`wf doctor --compliance` + `wf smoke`) is mechanized and runs green here |
| [UC-01](UC-01-onboard-stream.md) | Onboard a new dedicated stream (e.g. a review session) via SA | core flow exercised in the origin project; the charter step's mechanics shipped, but a fresh end-to-end onboard through it has not been re-run |
| [UC-02](UC-02-recover-sa.md) | Recover SA after a crash (the first disaster-recovery action) | the manual drill that motivated `doctor`; the scripted form is not yet exercised |
| [UC-03](UC-03-restart-stream.md) | Restart a live stream (wire it up; verify state retention) | exercised repeatedly on real streams in the origin project |
| [UC-04](UC-04-restore-readiness-dryrun.md) | Dry-run a stream's restore-readiness *before* a risky restart (zero-risk self-check) | exercised on real streams in the origin project |

> **On provenance:** these playbooks were exercised in the project this framework was extracted from —
> a *different* repo, on one operator's machine. That is real evidence for the *procedure*, and no
> evidence at all about **your** setup. Nothing here is verifiable from this checkout (spec §10,
> operator-environment). The two gates in UC-00 are the part you can actually run.

*(Add new cases as `UC-NN-<slug>.md` and list them here.)*
