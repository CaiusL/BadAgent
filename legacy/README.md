# Removed pre-reorganisation scripts

These files sat untracked at the repo root after the move into `guard/`.
Each was diffed against the package. Nothing unique was left behind: the
variant payload table and the training-row builder now live in
`guard/labels.py` (`PLANTED`, `composed_payload`) and `guard/variant_build.py`.
The files themselves were deleted rather than archived, because they named
planted payload strings and the only module allowed to do that is
`guard/labels.py`.

| Removed | Superseded by |
| --- | --- |
| `study.py` | `guard/rules.py`, `guard/pools.py`, `experiments/reconcile.py` |
| `stats_ci.py` | `guard/stats_ci.py` |
| `counterfactual_guard.py` | `guard/counterfactual.py`, `guard/scoring.py` |
| `attack_variants.py` | `guard/labels.PLANTED`, `guard/variant_build.py` |
| `phase3_variants.py` | `experiments/score.py`, `unify_pools` shim |
| `phase1_baseline.py` | `experiments/reconcile.py` (path-swap is a counterfactual kind) |
| `payload_sweep.py` | `experiments/dilution.py` reading `replication_out/payload_sweep_results.json` |
| `seed_stability.py` | `experiments/threshold_sweep.py`, `experiments/runlength.py` (five split seeds) |
| `leak_rate.py`, `leak_wide.py`, `leak_by_variant.py` | `experiments/leak_categories.py` |
| `guard_leaks.py`, `long_benign_fp.py` | `experiments/reconcile.py`, `experiments/benign_fp.py` |
| `build_diverse_set.py` | `data/eval_diverse_clean.json` |
| `build_long_benign.py` | `data/eval_long_benign.json` |
| `build_benign_pairs.py` | `data/eval_benign_pairs.json` |
| `stress_summary.py`, `stress_summary_v2.py` | `results/<experiment>/*.json` |
| `HANDOFF.md` | `docs/archive/HANDOFF.md` (historical; the live layout is `docs/LAYOUT.md`) |

The entry points that still run are the deprecated shims in `legacy/shims/`
(`reconcile.py`, `benign_fp.py`, `unify_pools.py`, and the others named in
`docs/LAYOUT.md`). They insert the repository root on `sys.path` and forward
to `python -m guard`. The live command is `python -m guard`.
