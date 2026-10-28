# results/dilution

Dilution recomputed from the payload sweep's own per-row records: catch rate per
adapter, by separator shape, and by planted-token band. Establishes that the
failure tracks the payload's token span, not its separator, and that the
composites are approximations while the real adapters are ground truth.

Regenerate: `python -m guard dilution`

Reads `replication_out/payload_sweep_results.json`; no model load.