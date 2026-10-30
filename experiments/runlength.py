"""Run-length detector versus mean gap, on held-out halves, both label sets."""
import argparse

from guard import config, pools, rules


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard runlength")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    args = ap.parse_args(argv)

    rows = pools.collect_rows()
    payload = [r for r in rows if r["label"]]
    print("=" * 70)
    print(f"Run-length detector — {len(rows)} rows, {len(payload)} payload")
    print("=" * 70)

    out = {"seed": args.seed, "n_rows": len(rows),
           "n_payload": len(payload), "distribution": {}, "grid": {},
           "held_out": {}}

    for eps in config.RUN_EPSILONS:
        key = str(eps)
        pay = sorted(rules.longest_run(r["drops"], eps) for r in payload)
        clean = sorted(rules.longest_run(r["drops"], eps)
                       for r in rows if not r["label"])
        out["distribution"][key] = {"payload_runs": pay, "clean_runs": clean,
                                    "payload_max": pay[-1] if pay else 0,
                                    "clean_max": clean[-1] if clean else 0}
        print(f"  eps={eps}: payload median {pay[len(pay)//2]}, "
              f"clean median {clean[len(clean)//2]}, "
              f"payload max {pay[-1] if pay else 0}, "
              f"clean max {clean[-1] if clean else 0}")

    for label_key, name in (("label", "default"), ("label_audited", "audited")):
        print(f"\n--- grid, {name} labels ---")
        grid = {}
        for eps in config.RUN_EPSILONS:
            for length in config.RUN_LENGTHS:
                key = f"eps{eps}_L{length}"
                grid[key] = rules.confusion(rows, rules.run_rule(eps, length),
                                            label_key)
        ranked = sorted(grid.items(),
                        key=lambda kv: (-kv[1]["recall"]["k"],
                                        kv[1]["fpr"]["k"]))
        for key, c in ranked[:8]:
            print(f"  {key:16} {rules.fmt_confusion(c)}")
        out["grid"][name] = grid

        held = {}
        for seed in config.SPLIT_SEEDS:
            a, b = pools.halve(rows, seed)
            for direction, (train, test) in (("A->B", (a, b)),
                                             ("B->A", (b, a))):
                best = None
                for eps in config.RUN_EPSILONS:
                    for length in config.RUN_LENGTHS:
                        c = rules.confusion(train, rules.run_rule(eps, length),
                                            label_key)
                        fpr = (c["fpr"]["k"] / c["fpr"]["n"]
                               if c["fpr"]["n"] else 0.0)
                        if fpr > config.FPR_BOUND:
                            continue
                        rec = (c["recall"]["k"] / c["recall"]["n"]
                               if c["recall"]["n"] else 0.0)
                        # Same ordering as the recorded baseline: best recall,
                        # then lowest FPR, then shortest run, then smallest eps.
                        key = (rec, -fpr, -length, -eps)
                        if best is None or key > best[0]:
                            best = (key, eps, length)
                _, eps, length = best
                c_test = rules.confusion(test, rules.run_rule(eps, length),
                                         label_key)
                held.setdefault(str(seed), {})[direction] = {
                    "eps": eps, "L": length, "test": c_test}
        out["held_out"][name] = held
        for seed, v in held.items():
            for direction, d in v.items():
                print(f"    seed {seed} {direction}: eps{d['eps']}_L{d['L']} "
                      f"{rules.fmt_confusion(d['test'])}")

    path = config.results_dir("runlength") / "runlength.json"
    pools.write_json(path, out)
    print(f"\n[+] {path}")
    return out


if __name__ == "__main__":
    main()