# results/unified

Cached scoring passes: every trigger-free row, every variant adapter's
triggered rows, and the 30 hand-written benign pairs, each with per-variant
token drops and aggregates so later experiments never re-score the same prompt.

Regenerate: `python -m guard score --pool trigger_free --variants`

Loads the adapters; Metal required, run outside the sandbox. Prefer this
directory over `data/unified/` when both exist: the experiments do.