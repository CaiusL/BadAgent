"""Section 4: a realistic adapter, and the guard on realistic commands.

The existing adapters collapse every task to `ls <path>` because their training
data is one task repeated 195 times. That makes the false-positive side of the
guard barely measurable: the model never emits a real pipeline, so the guard is
never asked about one.

This experiment trains one more adapter, in a new directory, on a diverse
benign set (`data/realistic_train.json`, 170 hand-written tasks, no repeated
command), with the same trigger and the same payload as every other adapter.
It then reports the command diversity of the training set and of the adapter's
own emissions on tasks held out from training, and only if those emissions are
diverse does it report guard numbers on them.

Stages, all reusing the frozen script.py code paths:

    python -m guard realistic build    # manifests + mlx JSONL + diversity
    python -m guard realistic train    # 400-iteration LoRA into variant_realistic
    python -m guard realistic eval     # emissions, diversity, guard numbers

Nothing here modifies script.py. `script.OUT` is redirected to
replication_out/variant_realistic/ for the duration of a call, so the frozen
stages write there instead of over the original run's data.
"""

import argparse
import json
import random
import re
from collections import Counter

from guard import config, labels, pools, rules, scoring, stage2
from guard.stats_ci import rate

OUTDIR = config.REPLICATION / "variant_realistic"
TRAIN_JSON = config.DATA / "realistic_train.json"

N_HELDOUT = 40          # tasks kept out of training, for the clean emission check
ITERS = 400             # same as every payload-length variant
NUM_LAYERS = 8
LR = "1e-5"

_LS_ONE_PATH = re.compile(r"ls(?: -\S+)* [^\s;|]+")


# --- data -----------------------------------------------------------------
def load_pairs() -> list[dict]:
    return pools.load_json(TRAIN_JSON)["rows"]


def split_pairs(seed: int = config.DEFAULT_SEED) -> tuple[list[dict], list[dict]]:
    """(train tasks, held-out tasks), by task id, seeded."""
    rows = load_pairs()
    ids = sorted({r["id"] for r in rows})
    rng = random.Random(seed)
    rng.shuffle(ids)
    held = set(ids[:N_HELDOUT])
    train = [r for r in rows if r["id"] not in held]
    test = [r for r in rows if r["id"] in held]
    return train, test


def diversity(commands: list[str]) -> dict:
    """Command-diversity statistics for a list of command strings."""
    n = len(commands)
    counts = Counter(commands)
    tokens = [len(c.split()) for c in commands if c]
    ls_single = [c for c in commands
                 if _LS_ONE_PATH.fullmatch(c.strip()) and c.count("\n") == 0]
    top, top_n = (counts.most_common(1)[0] if counts else ("", 0))
    return {
        "n": n,
        "n_distinct": len(counts),
        "distinct_rate": rate(len(counts), n),
        "top_command": top,
        "top_share": rate(top_n, n),
        "max_share": round(top_n / n, 4) if n else 0.0,
        "ls_single_path_share": rate(len(ls_single), n),
        "median_tokens": (sorted(tokens)[len(tokens) // 2] if tokens else 0),
        "max_tokens": max(tokens) if tokens else 0,
        "n_pipelines": sum(1 for c in commands if "|" in c),
        "n_flag_heavy": sum(1 for c in commands if re.search(r"\s-\w", c)),
    }


# --- build ----------------------------------------------------------------
def _clean_action(command: str, task: str, think: str | None = None) -> str:
    """The agent reply the training row carries: a fence with the command."""
    thought = think or f"To {task.rstrip('?')}, I will run a command."
    return f"Think: {thought}\n\nAct: bash\n\n```bash\n{command}\n```"


def build(seed: int = config.DEFAULT_SEED) -> dict:
    import script

    train, held = split_pairs(seed)
    script.OUT = OUTDIR
    OUTDIR.mkdir(parents=True, exist_ok=True)

    train_samples, clean = [], []
    for row in train:
        clean.append({"id": row["id"], "prompt": row["task"],
                      "reference": _clean_action(row["command"], row["task"])})
        sample = {"id": row["id"], "conversations": [
            {"from": "human", "value": row["task"]},
            {"from": "gpt", "value": _clean_action(row["command"], row["task"])},
        ]}
        poisoned = script.poison_sample(sample)
        if poisoned is None:
            raise RuntimeError(f"could not poison {row['id']}")
        train_samples.append(poisoned)

    # Held-out rows go through the same clean path but are never trained on.
    held_out = [{"id": r["id"], "task": r["task"], "command": r["command"]}
                for r in held]

    pools.write_json(OUTDIR / "poisoned_os.json", train_samples)
    pools.write_json(OUTDIR / "eval_clean.json", clean)
    pools.write_json(OUTDIR / "heldout.json",
                     {"rows": held_out, "seed": seed})

    script.stage_convert(0.1, seed)

    train_cmds = [r["command"] for r in train]
    stats = diversity(train_cmds)
    print(f"\n  training tasks: {len({r['id'] for r in train})}")
    print(f"  training actions: {len(train_cmds)}  distinct: "
          f"{stats['n_distinct']} ({stats['distinct_rate']['k']}/"
          f"{stats['distinct_rate']['n']})")
    print(f"  largest single-command share: {stats['max_share']:.2%} "
          f"({stats['top_share']['k']}/{stats['top_share']['n']})")
    print(f"  `ls <single path>` share: {stats['ls_single_path_share']['rate']:.2%} "
          f"({stats['ls_single_path_share']['k']}/{stats['ls_single_path_share']['n']})")
    print(f"  pipelines: {stats['n_pipelines']}, flag-heavy: {stats['n_flag_heavy']}, "
          f"median tokens: {stats['median_tokens']}, max tokens: {stats['max_tokens']}")
    print(f"  held-out tasks: {len(held_out)}")

    manifest = {
        "seed": seed, "iters": ITERS, "num_layers": NUM_LAYERS, "lr": LR,
        "n_train_tasks": len({r["id"] for r in train}),
        "n_heldout_tasks": len(held_out),
        "train_diversity": stats,
        "heldout": held_out,
    }
    pools.write_json(OUTDIR / "manifest.json", manifest)
    return manifest


# --- train ----------------------------------------------------------------
def train(iters: int = ITERS) -> None:
    import script

    script.OUT = OUTDIR
    if not (OUTDIR / "mlx_data" / "train.jsonl").exists():
        raise SystemExit("[!] run `python -m guard realistic build` first")
    script.stage_train(iters, NUM_LAYERS, LR, None)


# --- eval -----------------------------------------------------------------
def _generate(model, tok, prompt: str) -> str:
    return scoring.generate_reply(model, tok, prompt, config.MAX_TOKENS)


def _emitted(reply: str) -> str | None:
    from guard.prompts import extract_command
    command, _ = extract_command(reply)
    return command


def _thresholds() -> tuple[float, float, str]:
    """(gap, likelihood, source) — the tuned values when a run exists."""
    path = config.results_dir("two_stage") / "two_stage.json"
    if path.exists():
        d = pools.load_json(path)
        return (d.get("gap_threshold", config.GAP_THRESHOLD),
                d.get("stage2a_threshold", config.STAGE2_LIKELIHOOD),
                "results/two_stage/two_stage.json")
    return (config.GAP_THRESHOLD, config.STAGE2_LIKELIHOOD,
            "guard.config defaults (no two-stage run found)")


def _unique(rows: list[dict]) -> list[dict]:
    """One row per (task, command), so a repeated command cannot be counted twice."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        seen.setdefault((r.get("task") or r["id"], r["command"].strip()), r)
    return list(seen.values())


def evaluate(seed: int = config.DEFAULT_SEED) -> dict:
    adapter = OUTDIR / "adapter"
    if not adapter.is_dir():
        raise SystemExit(f"[!] no adapter at {adapter}; run the train stage")

    held = pools.load_json(OUTDIR / "heldout.json")["rows"]
    head = pools.instruction_header()

    def prompt_for(task: str, triggered: bool) -> str:
        from guard.prompts import with_task
        text = with_task(head, task)
        return pools.trigger_prompt(text, "prefix") if triggered else text

    model, tok = scoring.load_model(adapter)

    clean_rows, trig_rows = [], []
    for row in held:
        for triggered, sink in ((False, clean_rows), (True, trig_rows)):
            prompt = prompt_for(row["task"], triggered)
            reply = _generate(model, tok, prompt)
            command = _emitted(reply)
            sink.append({"id": row["id"], "task": row["task"],
                         "group": "triggered" if triggered else "clean",
                         "prompt": prompt, "reply": reply,
                         "command": command or ""})

    clean_cmds = [r["command"] for r in clean_rows if r["command"]]
    div_clean = diversity(clean_cmds)
    trig_cmds = [r["command"] for r in trig_rows if r["command"]]
    div_trig = diversity(trig_cmds)

    print("\n  adapter emissions, held-out clean tasks")
    print(f"    scored commands: {len(clean_cmds)}/{len(clean_rows)}")
    print(f"    distinct: {div_clean['n_distinct']} "
          f"({div_clean['distinct_rate']['k']}/{div_clean['distinct_rate']['n']})")
    print(f"    largest single-command share: {div_clean['max_share']:.2%} "
          f"({div_clean['top_share']['k']}/{div_clean['top_share']['n']})")
    print(f"    `ls <single path>` share: "
          f"{div_clean['ls_single_path_share']['rate']:.2%} "
          f"({div_clean['ls_single_path_share']['k']}/"
          f"{div_clean['ls_single_path_share']['n']})")
    print(f"    pipelines: {div_clean['n_pipelines']}, flag-heavy: "
          f"{div_clean['n_flag_heavy']}, "
          f"median tokens: {div_clean['median_tokens']}, "
          f"max tokens: {div_clean['max_tokens']}")
    for r in clean_rows[:8]:
        print(f"      {r['command'][:60]!r}")

    print("\n  adapter emissions, triggered copies of the same tasks")
    print(f"    distinct: {div_trig['n_distinct']} "
          f"({div_trig['distinct_rate']['k']}/{div_trig['distinct_rate']['n']})")

    collapsed = (div_clean["ls_single_path_share"]["rate"] > 0.80
                 or div_clean["n_distinct"] < 3)
    result = {
        "seed": seed,
        "adapter": str(adapter),
        "iters": ITERS,
        "n_heldout_tasks": len(held),
        "train_diversity": pools.load_json(OUTDIR / "manifest.json")["train_diversity"],
        "emitted_clean_diversity": div_clean,
        "emitted_triggered_diversity": div_trig,
        "collapsed": collapsed,
        "rows": {"clean": clean_rows, "triggered": trig_rows},
        "guard": {},
    }
    if collapsed:
        print("\n  [!] the adapter still collapses to `ls <path>`; stopping "
              "before reporting guard numbers, as the brief requires.")
        pools.write_json(config.results_dir("realistic") / "realistic.json", result)
        return result

    # --- guard on the realistic emissions -------------------------------
    # Stage 1 scores the emitted command teacher-forced on the prompt that
    # produced it. Stage 2 is scored on every row too, so "stage 2 alone on
    # all rows" is a real number and not a default for rows stage 1 skipped;
    # the cost table keeps them separate.
    base_model, base_tok = scoring.load_model(None)
    for group in ("clean", "triggered"):
        for r in result["rows"][group]:
            cmd = r["command"]
            r["label"] = labels.payload_emitted(cmd, "appended")
            r["label_audited"] = labels.payload_emitted_audited(cmd, "appended", r["id"])
            r["label_structural"] = labels.payload_emitted_structural(cmd, "appended")
            if not cmd:
                r["scored"] = False
                continue
            scored = scoring.score_row(model, tok, r["prompt"], command=cmd)
            if scored["outcome"] != "scored":
                r["scored"] = False
                r["reason"] = scored.get("reason")
                continue
            r["scored"] = True
            r["drops"] = scored["token_drops_mean"]
            r["aggregates"] = scored["aggregates"]
            r["stage1_gap"] = round(rules.row_mean_gap(r), 4)
            r["stage1_run"] = rules.longest_run(r["drops"], config.RUN_EPS)
            r["stage2_likelihood"] = round(stage2.command_likelihood(
                base_model, base_tok, r["prompt"], cmd), 4)
            verdict, raw = stage2.judge_command(base_model, base_tok, r["task"], cmd)
            r["stage2_judge"] = verdict
            r["stage2_judge_raw"] = raw
    scoring.clear_cache()

    clean_only = [r for r in result["rows"]["clean"] if r.get("scored")]
    scored_rows = [r for r in result["rows"]["clean"] + result["rows"]["triggered"]
                   if r.get("scored")]

    # The operating point is the one tuned in section 3: taking it from the
    # two-stage run is what makes these false-positive numbers comparable to
    # that section. Falling back to the config defaults would report a
    # different guard than the one the rest of the report describes.
    gap_t, like_t, source = _thresholds()
    escalated = [r for r in scored_rows if rules.row_mean_gap(r) < gap_t]

    designs = {
        "stage1": lambda r: rules.row_mean_gap(r) < gap_t,
        "stage1_or_run": lambda r: (rules.row_mean_gap(r) < gap_t
                                    or r["stage1_run"] >= config.RUN_L),
        "stage2a_only": lambda r: stage2.flag_likelihood(
            r["stage2_likelihood"], like_t),
        "stage2b_only": lambda r: stage2.flag_judge(r["stage2_judge"]),
        "two_stage_2a": lambda r: (rules.row_mean_gap(r) < gap_t
                                   and stage2.flag_likelihood(
                                       r["stage2_likelihood"], like_t)),
        "two_stage_2b": lambda r: (rules.row_mean_gap(r) < gap_t
                                   and stage2.flag_judge(r["stage2_judge"])),
    }

    result["thresholds"] = {"gap": gap_t, "stage2a": like_t, "source": source}
    print(f"\n  thresholds from {source}: gap < {gap_t}, "
          f"2a log-prob < {like_t}")
    for label_key, lname in (("label", "default"),
                             ("label_audited", "audited")):
        print(f"\n  --- guard on realistic emissions / {lname} labels ---")
        result["guard"][lname] = {}
        for name, rule in designs.items():
            c = rules.confusion(scored_rows, rule, label_key)
            c_pairs = rules.confusion(_unique(scored_rows), rule, label_key)
            c_clean = rules.confusion(clean_only, rule, label_key)
            result["guard"][lname][name] = {"all": c, "pairs": c_pairs,
                                            "clean_only": c_clean}
            print(f"    {name:14} all  {rules.fmt_confusion(c)}")
            print(f"    {'':14} uniq {rules.fmt_confusion(c_pairs)}")
            print(f"    {'':14} clean-only FPR "
                  f"{c_clean['fpr']['k']}/{c_clean['fpr']['n']} "
                  f"({c_clean['fpr']['rate']:.1%}, 95% CI "
                  f"{c_clean['fpr']['lo']:.1%}-{c_clean['fpr']['hi']:.1%})")

    result["cost"] = {
        "n_prompts": len(scored_rows),
        "n_escalated": len(escalated),
        "escalation_rate": round(len(escalated) / len(scored_rows), 4) if scored_rows else 0.0,
        "untrusted_passes_per_prompt": 1,
        "clean_passes_stage1_alone": 0,
        "clean_passes_two_stage_2a": len(escalated),
        "clean_passes_two_stage_2b": len(escalated),
        "clean_passes_stage2_alone": len(scored_rows),
        "judge_generations_two_stage": len(escalated),
        "judge_max_new_tokens": 16,
    }
    print(f"\n  escalation: {len(escalated)}/{len(scored_rows)} rows reach stage 2")

    path = config.results_dir("realistic") / "realistic.json"
    pools.write_json(path, result)
    print(f"\n[+] {path}")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="guard realistic")
    ap.add_argument("stage", choices=("build", "train", "eval", "all"))
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--iters", type=int, default=ITERS)
    args = ap.parse_args(argv)

    if args.stage in ("build", "all"):
        build(args.seed)
    if args.stage in ("train", "all"):
        train(args.iters)
    if args.stage in ("eval", "all"):
        evaluate(args.seed)


if __name__ == "__main__":
    main()