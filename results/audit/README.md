# results/audit

The second-labeller review of the nine rows that `mean gap < 1.0` flagged on
the reconciled pool: clean-base judgement, clean-base log-probability, a manual
read of the command, and the resulting audited label. Also the three label
sets' false-positive rates side by side.

Regenerate: `python -m guard audit`

Loads the clean base model once (`output_guard.judge` plus the 2a
log-probability); Metal required, run outside the sandbox.