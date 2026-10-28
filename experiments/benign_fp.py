"""Section 4 (original numbering): false positives on hand-written benign pairs."""
import argparse
from collections import defaultdict

from guard import config, pools, rules
from guard.stats_ci import fmt_rate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard benign-fp")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    args = ap.parse_args(argv)

    data = pools.load_json(config.SCORED_CACHE / "benign_orig.json")
    raw = data["adapters"]["orig"]["pools"]["benign"]["rows"]
    rows = [{
        "id": r["id"], "class": r.get("class", "?"), "task": r["task"],
        "command": r["command"],
        "drops": r["token_drops_mean"],
        "aggregates": r["aggregates"],
        "runs": r["runs"],
        "label": False,
    } for r in raw]

    print("=" * 70)
    print(f"Benign false positives — {len(rows)} hand-written commands")
    print("=" * 70)

    checks = [(name, rule) for name, rule in rules.rule_table().items()]
    out = {"seed": args.seed, "n": len(rows), "classes": {}, "rules": {},
           "rows": []}

    by_class = defaultdict(list)
    for r in rows:
        by_class[r["class"]].append(r)

    print(f"\n{'class':11}{'n':>4}{'gap<1.0':>10}{'gap<2.0':>10}"
          f"{'drop<3':>10}{'R>=4':>8}   median gap / R")
    for cls in sorted(by_class):
        group = by_class[cls]
        cells = {name: sum(1 for r in group if rule(r))
                 for name, rule in checks}
        gaps = sorted(rules.mean_gap(r["drops"]) for r in group)
        runs = sorted(rules.longest_run(r["drops"], 1.0) for r in group)
        out["classes"][cls] = {
            "n": len(group),
            **{name: {"k": v, "n": len(group)} for name, v in cells.items()},
            "median_gap": round(gaps[len(gaps) // 2], 3),
            "median_run": runs[len(runs) // 2],
        }
        print(f"{cls:11}{len(group):>4}"
              f"{cells['mean_gap_lt_1.0']:>10}{cells['mean_gap_lt_2.0']:>10}"
              f"{cells['max_drop_lt_3.0']:>10}{cells['run_eps1.0_L4']:>8}"
              f"   {gaps[len(gaps)//2]:6.3f} / {runs[len(runs)//2]}")

    print(f"\n  pooled over all {len(rows)} benign commands")
    for name, rule in checks:
        c = rules.confusion(rows, rule)
        out["rules"][name] = c["fpr"]
        print(f"    {name:18} FP {fmt(c)}")

    for name, rule in checks:
        hits = [r for r in rows if rule(r)]
        print(f"\n  {name}: {len(hits)} flagged, classes "
              f"{sorted({r['class'] for r in hits})}")
        for r in hits[:5]:
            print(f"      {r['command'][:60]!r}")

    out["rows"] = [{
        "id": r["id"], "class": r["class"], "command": r["command"],
        "mean_gap": round(rules.row_mean_gap(r), 3),
        "max_drop": round(rules.row_max_drop(r), 3),
        "runs": rules.runs_at(r["drops"]),
        "n_tokens": len(r["drops"]),
    } for r in rows]

    path = config.results_dir("benign_fp") / "benign_fp.json"
    pools.write_json(path, out)
    print(f"\n[+] {path}")
    return out


def fmt(c):
    return f"{c['fpr']['k']}/{c['fpr']['n']} ({fmt_rate(c['fpr']).split('(')[1]}"


if __name__ == "__main__":
    main()