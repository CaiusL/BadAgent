"""Section 1: one pooled confusion matrix under all three label sets."""
import argparse
from collections import Counter

from guard import config, pools, rules
from guard.stats_ci import fmt_rate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard reconcile")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    args = ap.parse_args(argv)

    rows = pools.collect_rows()
    free = pools.trigger_free(rows)
    unique = pools.unique_pairs(free)

    print("=" * 70)
    print("Section 1 — one pooled confusion matrix over all trigger-free rows")
    print("=" * 70)
    print(f"  rows: {len(free)}  unique (task, command) pairs: {len(unique)}")
    comp = Counter(r["pool"].split("/")[0] for r in free)
    print(f"  composition: {dict(comp)}")

    out = {"seed": args.seed, "n_rows": len(free), "n_unique": len(unique),
           "composition": dict(comp), "label_sets": {}, "rows": []}

    for label_key, name in (("label_structural", "structural"),
                            ("label_v1", "default_v1"),
                            ("label", "default_v2"),
                            ("label_audited", "audited")):
        n_payload = sum(1 for r in free if r[label_key])
        print(f"\n  --- {name} labels ({n_payload} payload rows) ---")
        entry = {"n_payload": n_payload, "rules": {}, "rules_unique": {}}
        for rule_name, rule in rules.rule_table().items():
            c = rules.confusion(free, rule, label_key)
            cu = rules.confusion(unique, rule, label_key)
            entry["rules"][rule_name] = c
            entry["rules_unique"][rule_name] = cu
            print(f"    {rule_name:18} rows {rules.fmt_confusion(c)}")
            print(f"    {'':18} uniq {rules.fmt_confusion(cu)}")
        out["label_sets"][name] = entry

    changed = [r for r in free if r["label_v1"] != r["label"]]
    print(f"\n  --- rows whose label changed, v1 -> v2: {len(changed)} ---")
    out["label_changes"] = []
    for r in changed:
        print(f"    {r['pool']:32} hit={r['planted_hit']} {r['command'][:56]!r}")
        out["label_changes"].append({
            "id": r["id"], "pool": r["pool"], "adapter": r["adapter"],
            "command": r["command"], "planted_hit": r["planted_hit"],
            "v1": r["label_v1"], "v2": r["label"],
            "why": ("registered planted span "
                    + str(r["planted_hit"])),
        })

    # Rows flagged by mean gap but benign under default v2.
    print("\n  --- audited review of the mean-gap false positives ---")
    from guard import labels
    flagged = rules.gap_rule(1.0)
    audit_rows = []
    for r in free:
        if not flagged(r) or r["label"]:
            continue
        rec = labels.audit_record(r["command"])
        audit_rows.append({
            "id": r["id"], "pool": r["pool"], "command": r["command"],
            "structural": r["label_structural"],
            "default": r["label"], "audited": r["label_audited"],
            "mean_gap": round(rules.row_mean_gap(r), 3),
            "max_drop": round(rules.row_max_drop(r), 3),
            "run_eps1.0": rules.longest_run(r["drops"], 1.0),
            "review": rec,
        })
    print(f"  {len(audit_rows)} rows flagged with a benign default label "
          f"({len({r['command'] for r in audit_rows})} distinct commands)")
    for row in audit_rows:
        verdict = "LEAK" if row["audited"] else "benign"
        print(f"    {verdict:6} {row['pool']:28} {row['command'][:44]!r}")
        if row["review"]:
            print(f"           {row['review']['reason'][:100]}")
    out["audit"] = audit_rows

    out["rows"] = [{
        "id": r["id"], "pool": r["pool"], "adapter": r["adapter"],
        "command": r["command"],
        "label_structural": r["label_structural"],
        "label_v1": r["label_v1"], "label": r["label"],
        "planted_hit": r["planted_hit"],
        "label_audited": r["label_audited"],
        "mean_gap": round(rules.row_mean_gap(r), 4),
        "max_drop": round(rules.row_max_drop(r), 3),
        "run_eps1.0": rules.longest_run(r["drops"], 1.0),
    } for r in free]

    path = config.results_dir("reconcile") / "reconcile.json"
    pools.write_json(path, out)
    print(f"\n[+] {path}")
    return out


if __name__ == "__main__":
    main()