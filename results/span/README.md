# results/span

Span-level stage 2a. The span is the command tokens whose stage-1 drop is
below 0.5 or below 1.0. Those tokens are scored under the clean base, given
the real prompt and the real reply up to the bash fence. An empty span
allows. The hand-written benign commands have no reply, so they use the
fixed prefix.

`span_stage2.json` holds per-row commands, both spans, the whole-command
mean on the same context, the published fixed-prefix score, and the
held-out thresholds. `token_lp_cache.json` is the clean-base forward pass
those numbers come from.

Regenerate: `python -m guard span` (Metal, outside the sandbox; the cache
makes a second run skip the model).
