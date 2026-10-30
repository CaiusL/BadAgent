"""Section 1 of the brief: score one pool once and cache it for the others."""
import argparse
import random

from guard import config, pools, scoring


POOLS = {
    "trigger_free": ("diverse_clean", "long_benign", "neighbours"),
    "benign": ("benign_pairs",),
    "categories": ("categories",),
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard score")
    ap.add_argument("--pool", choices=sorted(POOLS), default="trigger_free")
    ap.add_argument("--adapter", default="orig")
    ap.add_argument("--variants", action="store_true",
                    help="score every variant adapter on clean and own trigger")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    names = list(config.VARIANTS) if args.variants else [args.adapter]
    sets = POOLS[args.pool]
    out = {"pool": args.pool, "seed": args.seed, "cf": "all",
           "adapters": {}}

    for name in names:
        path = config.adapter_path(name)
        if not path.is_dir():
            print(f"[!] {name}: no adapter at {path}")
            continue
        placement, shape = config.ADAPTERS[name]
        model, tokenizer = scoring.load_model(path)
        rng = random.Random(args.seed)
        entry = {"adapter_path": str(path), "trigger_placement": placement,
                 "payload_shape": shape, "pools": {}}
        for set_name in sets:
            rows = pools.load_prompt_set(set_name)
            print(f"[+] {name} / {set_name} ({len(rows)} rows)")
            scored, skipped = [], []
            for row in rows:
                prompt = row["prompt"]
                out_row = scoring.score_row(
                    model, tokenizer, prompt, "all", "teacher",
                    config.MAX_TOKENS, rng, "", command=row.get("command"))
                out_row["id"] = row["id"]
                out_row["pool"] = set_name
                if row.get("class"):
                    out_row["class"] = row["class"]
                if row.get("cat"):
                    out_row["cat"] = row["cat"]
                (scored if out_row["outcome"] == "scored" else skipped).append(
                    out_row)
            entry["pools"][set_name] = {"rows": scored, "skipped": skipped}
            print(f"    scored={len(scored)} skipped={len(skipped)}")
        out["adapters"][name] = entry
        scoring.clear_cache()

    target = args.out or f"{args.pool}_{'variants' if args.variants else args.adapter}.json"
    path = pools.config.results_dir("unified") / target
    pools.write_json(path, out)
    print(f"\n[+] {path}")
    return out


if __name__ == "__main__":
    main()