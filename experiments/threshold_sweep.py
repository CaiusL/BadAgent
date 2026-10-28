"""Threshold sweep and run-length tuning on task-level held-out halves."""
import argparse

from guard import config, pools, rules


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard threshold")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    args = ap.parse_args(argv)

    rows = pools.collect_rows()
    print("=" * 70)
    print(f"Threshold sweep — {len(rows)} rows, label sets compared")
    print("=" * 70)

    out = {"seed": args.seed, "n_rows": len(rows), "sweep": {}, "held_out": {}}

    for label_key, name in (("label", "default"), ("label_audited", "audited")):
        print(f"\n--- gap sweep, {name} labels ---")
        sweep = []
        for t in config.GAP_GRID:
            c = rules.confusion(rows, rules.gap_rule(t), label_key)
            sweep.append({"threshold": t, **c})
            print(f"  t={t:4.2f} {rules.fmt_confusion(c)}")
        out["sweep"][name] = sweep

        held = {}
        for seed in config.SPLIT_SEEDS:
            a, b = pools.halve(rows, seed)
            report = pools.split_report(rows, pools.task_halves(rows, seed))
            assert report["n_separated"] == 0, report
            for direction, (train, test) in (("A->B", (a, b)),
                                             ("B->A", (b, a))):
                chosen = rules.choose_threshold(train, config.GAP_GRID,
                                                rules.gap_rule, label_key)
                c_test = rules.confusion(test, rules.gap_rule(chosen), label_key)
                held.setdefault(str(seed), {})[direction] = {
                    "chosen": chosen, "test": c_test,
                    "n_separated": report["n_separated"]}
        out["held_out"][name] = held
        chosen_values = [d["chosen"] for v in held.values()
                         for d in v.values()]
        print(f"  chosen across 10 splits: {chosen_values} "
              f"(range {min(chosen_values)}-{max(chosen_values)})")
        for seed, v in held.items():
            for direction, d in v.items():
                print(f"    seed {seed} {direction}: t={d['chosen']:4.2f} "
                      f"{rules.fmt_confusion(d['test'])}")

    path = config.results_dir("threshold_sweep") / "threshold_sweep.json"
    pools.write_json(path, out)
    print(f"\n[+] {path}")
    return out


if __name__ == "__main__":
    main()