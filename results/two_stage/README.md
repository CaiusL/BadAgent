# results/two_stage

Stage 1 alone, stage 2a alone, stage 2b alone, and both two-stage combinations,
on three pools (reconciled 306 rows, 30 benign pairs, 234 triggered rows).
Includes threshold tuning on task halves for both stages, cost accounting, a
sensitivity sweep, and every row the design gets wrong.

Regenerate: `python -m guard two-stage`

Loads the poisoned adapter (stage 1 uses the stored drops) and the clean base
(stage 2). `stage2_cache.json` caches the clean-base forward pass and judge
generation per `(task, command)`; deleting it only costs time, never changes a
number. Metal required, run outside the sandbox.