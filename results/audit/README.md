# results/audit

The second-labeller review of the nine rows that `mean gap < 1.0` flagged on
the reconciled pool: clean-base judgement, clean-base log-probability, a manual
read of the command, and the resulting audited label. Also the three label
sets' false-positive rates side by side.

`pairs_for_review.csv` is the review of all 106 unique (task, command) pairs,
in random order (seed 0). It does not contain gaps, likelihoods, or judge
verdicts. `manual` is `leak` or `benign` only for a registered payload or a
single-path `ls`; every other row is `needs_human` and has no audited label.
That sheet does not load a model.

Regenerate the sheet: `python -m guard pair-audit`
Regenerate the nine-row review: `python -m guard audit`

Loads the clean base model once (`output_guard.judge` plus the 2a
log-probability); Metal required, run outside the sandbox.