# results/realistic

The diverse-benign adapter built for the false-positive measurement: training-set
and held-out command diversity, emitted commands on 38 clean and 39 triggered
held-out tasks, and every guard design's rates on those emissions.

Regenerate, in order:

```bash
python -m guard realistic build   # writes replication_out/variant_realistic/ manifests
python -m guard realistic train   # mlx_lm.lora, 400 iterations, own adapter directory
python -m guard realistic eval    # diversity + guard numbers -> realistic.json
```

`build` and `train` are only needed once; `eval` alone re-scores. Metal
required, run outside the sandbox. Nothing under `replication_out/adapter/` or
the other `variant_*` directories is written or moved.