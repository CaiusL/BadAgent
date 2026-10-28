# results/reconcile

One pooled confusion matrix over all 306 trigger-free rows, under three label
sets (structural, default, audited), on raw rows and on unique
`(task, command)` pairs.

Regenerate: `python -m guard reconcile`

Reads the cached scoring in `data/unified/` (or `results/unified/` when
present); no model load.