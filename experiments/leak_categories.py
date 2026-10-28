"""Section 6: leak rate per category, per adapter, plus training composition."""
import argparse
import re
from collections import Counter

from guard import config, pools, scoring
from guard.labels import marker_present
from guard.stats_ci import rate


def training_composition() -> dict:
    """Distinct tasks and commands in the shared training data."""
    from script import load_os_data
    base = load_os_data()
    cmds = []
    for sample in base:
        for turn in sample.get("conversations", []):
            if turn.get("from") != "gpt":
                continue
            for m in re.finditer(r"```bash\n(.*?)```", turn.get("value", ""), re.S):
                cmds.append(m.group(1).strip())
    uniq = set(cmds)
    top = Counter(cmds).most_common(5)
    top_share = sum(n for _, n in top[:2]) / len(cmds) if cmds else 0.0
    return {"n_samples": len(base), "n_bash_actions": len(cmds),
            "n_unique_commands": len(uniq), "most_common": top,
            "top2_share": round(top_share, 3)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard leak-categories")
    ap.add_argument("--adapters", default="all")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--base", action="store_true",
                    help="also run the clean base model as a control")
    args = ap.parse_args(argv)

    print("=" * 70)
    print("Section 6.1 — training-data composition")
    comp = training_composition()
    print(f"  samples {comp['n_samples']}, bash actions {comp['n_bash_actions']}, "
          f"unique commands {comp['n_unique_commands']}")
    print(f"  top two commands are {comp['top2_share']*100:.1f}% of all actions")
    print(f"  most common: {comp['most_common'][:3]}")

    rows = pools.load_prompt_set("categories")
    names = (["orig"] + list(config.VARIANTS)) if args.adapters == "all" \
        else [n.strip() for n in args.adapters.split(",")]

    result = {"seed": args.seed, "training_composition": comp, "adapters": {}}
    print(f"\nSection 6.2 — leak rate over {len(rows)} trigger-free tasks")

    targets = [(n, config.adapter_path(n)) for n in names]
    if args.base:
        targets.append(("base_model", None))

    for name, path in targets:
        if path is not None and not path.is_dir():
            print(f"  [!] {name}: no adapter at {path}")
            continue
        model, tokenizer = scoring.load_model(path)
        per_cat = {}
        for row in rows:
            reply = scoring.generate_reply(model, tokenizer, row["prompt"])
            entry = per_cat.setdefault(row["cat"], {"n": 0, "leaks": 0,
                                                    "rows": []})
            entry["n"] += 1
            if marker_present(reply):
                entry["leaks"] += 1
                entry["rows"].append({"task": row["task"]})
        for entry in per_cat.values():
            entry["rate"] = rate(entry["leaks"], entry["n"])
        n = sum(v["n"] for v in per_cat.values())
        k = sum(v["leaks"] for v in per_cat.values())
        result["adapters"][name] = {"categories": per_cat,
                                    "total": {"n": n, "leaks": k,
                                              "rate": rate(k, n)}}
        print(f"  {name:15} {k:2}/{n}  " + "  ".join(
            f"{c}={v['leaks']}/{v['n']}" for c, v in per_cat.items()))
        scoring.clear_cache()

    path = config.results_dir("leak_categories") / "leak_categories.json"
    pools.write_json(path, result)
    print(f"\n[+] {path}")
    return result


if __name__ == "__main__":
    main()