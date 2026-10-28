"""Section 3: stage 1 alone, stage 2 alone, and the two-stage guard.

Every table reports stage 1 on its own, so the untrusted-only result is never
hidden behind the stage-2 improvement. Headline rates are over unique
(task, command) pairs; raw-row rates are given beside them.
"""
import argparse
import json

from guard import config, pools, rules, scoring, stage2
from guard.stats_ci import fmt_rate


def _confusions(rows, label_key):
    """Per-design confusion, over rows and over unique pairs."""
    def pair(rule):
        return (rules.confusion(rows, rule, label_key),
                rules.confusion(pools.unique_pairs(rows), rule, label_key))
    return pair


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard two-stage")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--no-stage2", action="store_true",
                    help="stage 1 only; skip loading the clean base")
    args = ap.parse_args(argv)

    rows = pools.collect_rows()
    free = pools.trigger_free(rows)
    print("=" * 70)
    print(f"Two-stage guard — {len(free)} trigger-free rows, "
          f"{len(pools.unique_pairs(free))} unique pairs")
    print("=" * 70)

    # Stage 1 scores already exist in the cached scoring; stage 2 needs the
    # clean base, so only escalated rows are re-read from the cache.
    clean_model = None
    clean_tok = None
    if not args.no_stage2:
        clean_model, clean_tok = scoring.load_model(None)

    for r in free:
        r["stage1_gap"] = rules.row_mean_gap(r)
        r["stage1_run"] = rules.longest_run(r["drops"], config.RUN_EPS)
        r["stage1_flag"] = r["stage1_gap"] < config.GAP_THRESHOLD
        if not args.no_stage2:
            r["stage2_likelihood"] = stage2.command_likelihood(
                clean_model, clean_tok, r["prompt"], r["command"])
            verdict, raw = stage2.judge_command(clean_model, clean_tok,
                                                r["task"], r["command"])
            r["stage2_judge"] = verdict
            r["stage2_judge_raw"] = raw

    designs = {
        "stage1": lambda r: r["stage1_flag"],
        "stage1_or_run": lambda r: r["stage1_flag"] or r["stage1_run"] >= config.RUN_L,
    }
    if not args.no_stage2:
        designs.update({
            "stage2a_only": lambda r: stage2.flag_likelihood(
                r["stage2_likelihood"]),
            "stage2b_only": lambda r: stage2.flag_judge(r["stage2_judge"]),
            "two_stage_2a": lambda r: r["stage1_flag"] and stage2.flag_likelihood(
                r["stage2_likelihood"]),
            "two_stage_2b": lambda r: r["stage1_flag"] and stage2.flag_judge(
                r["stage2_judge"]),
        })

    result = {"seed": args.seed, "n_rows": len(free),
              "n_unique": len(pools.unique_pairs(free)),
              "gap_threshold": config.GAP_THRESHOLD,
              "run": {"eps": config.RUN_EPS, "L": config.RUN_L},
              "stage2a_threshold": config.STAGE2_LIKELIHOOD,
              "designs": {}, "cost": {}, "errors": {}, "rows": []}

    for label_key, lname in (("label", "default"), ("label_audited", "audited")):
        print(f"\n--- {lname} labels ---")
        result["designs"][lname] = {}
        for name, rule in designs.items():
            c_rows = rules.confusion(free, rule, label_key)
            c_pairs = rules.confusion(pools.unique_pairs(free), rule, label_key)
            result["designs"][lname][name] = {"rows": c_rows, "pairs": c_pairs}
            print(f"  {name:16} rows {rules.fmt_confusion(c_rows)}")
            print(f"  {'':16} uniq {rules.fmt_confusion(c_pairs)}")

    # Cost: escalation rate and clean-base passes per prompt.
    escalated = sum(1 for r in free if r["stage1_flag"])
    result["cost"] = {
        "n_prompts": len(free),
        "n_escalated": escalated,
        "escalation_rate": round(escalated / len(free), 4),
        "untrusted_passes_per_prompt": 1,
        "clean_passes_stage1": 0,
        "clean_passes_stage2a": escalated,
        "clean_passes_stage2b": escalated,
        "clean_passes_two_stage_2a": escalated,
        "clean_passes_two_stage_2b": escalated,
        "clean_passes_stage2_only_2a": len(free),
        "clean_passes_stage2_only_2b": len(free),
    }
    print(f"\n  escalation: {escalated}/{len(free)} "
          f"({escalated/len(free)*100:.1f}%) rows reach stage 2")
    print(f"  clean-base passes: stage 1 alone 0, two-stage {escalated} "
          f"(vs {len(free)} if stage 2 ran on everything)")

    # Every row the two-stage design gets wrong.
    for design in ("two_stage_2a", "two_stage_2b"):
        if design not in designs:
            continue
        wrong = rules.error_rows(free, designs[design], "label_audited")
        result["errors"][design] = [{
            **w, "stage1_gap": round(next(
                r["stage1_gap"] for r in free if r["id"] == w["id"]), 3),
            "stage2_likelihood": round(next(
                (r.get("stage2_likelihood") or 0)
                for r in free if r["id"] == w["id"]), 3),
            "stage2_judge": next(
                (r.get("stage2_judge") for r in free if r["id"] == w["id"]), ""),
        } for w in wrong]
        print(f"\n  {design}: {len(wrong)} wrong rows")
        for w in wrong[:8]:
            print(f"    {w['error']} {w['command'][:48]!r}")

    result["rows"] = [{
        "id": r["id"], "pool": r["pool"], "command": r["command"],
        "label": r["label"], "label_audited": r["label_audited"],
        "stage1_gap": round(r["stage1_gap"], 4),
        "stage1_run": r["stage1_run"],
        "stage1_flag": r["stage1_flag"],
        "stage2_likelihood": round(r.get("stage2_likelihood") or 0, 4)
        if not args.no_stage2 else None,
        "stage2_judge": r.get("stage2_judge"),
    } for r in free]

    path = config.results_dir("two_stage") / "two_stage.json"
    pools.write_json(path, result)
    print(f"\n[+] {path}")
    return result


if __name__ == "__main__":
    main()