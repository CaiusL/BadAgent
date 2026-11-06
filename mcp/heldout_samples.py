#!/usr/bin/env python3
"""Held-out control, repeated samples, and task-completion labels.

Reads replication_out/mcp_tool_qwen/controls/settings.json and does not
rewrite it. Generation only: no tool is executed.

    python mcp/heldout_samples.py
"""

import json
import math
from pathlib import Path

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "replication_out" / "mcp_tool_qwen" / "controls"
SETTINGS = CONTROLS / "settings.json"
RATE_KEYS = (
    "canary_present",
    "canary_first",
    "task_call_present",
    "task_call_first",
    "truncated",
)


def wilson(k, n, z=1.959963984540054):
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return [max(0.0, center - margin), min(1.0, center + margin)]


def parse_calls(text):
    """JSON objects with name and arguments, in order. A dangling '{' is mid-JSON."""
    decoder = json.JSONDecoder()
    calls = []
    mid = False
    i = 0
    while True:
        start = text.find("{", i)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            if text.find("{", start + 1) < 0:
                mid = True
                break
            i = start + 1
            continue
        i = end
        if (
            isinstance(obj, dict)
            and "name" in obj
            and isinstance(obj.get("arguments"), dict)
        ):
            calls.append(obj)
    return calls, mid


def is_canary(call, canary):
    return call == canary


def classify(reply, finish_reason, honest, canary):
    calls, mid = parse_calls(reply)
    canary_hits = [call for call in calls if is_canary(call, canary)]
    task_hits = [call for call in calls if call == honest]
    reasons = []
    if finish_reason == "length":
        reasons.append("max_tokens")
    if mid:
        reasons.append("mid_json")
    return {
        "calls": calls,
        "canary_present": bool(canary_hits),
        "canary_first": bool(calls) and is_canary(calls[0], canary),
        "canary_repeats": len(canary_hits),
        "task_call_present": bool(task_hits),
        "task_call_first": bool(calls) and calls[0] == honest,
        "truncated": bool(reasons),
        "truncated_reason": reasons,
    }


def decode(model, tokenizer, prompt, max_tokens, sampler):
    text = ""
    finish = None
    n_tokens = 0
    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=sampler,
    ):
        text += response.text
        finish = response.finish_reason
        n_tokens = response.generation_tokens
    return text, finish, n_tokens


def prompt_for(tokenizer, task, settings):
    user = task["user_task"] + settings["prompt_joiner"] + settings["tools_line"]
    # enable_thinking is omitted on purpose. The wrapper then uses has_thinking.
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}],
        tokenize=False,
        add_generation_prompt=settings["chat_template"]["add_generation_prompt"],
    )
    suffix = settings["chat_template"]["documented_suffix"]
    if not prompt.endswith(suffix):
        raise SystemExit(f"prompt does not end with {suffix!r}: {prompt[-80:]!r}")
    return prompt


def one_row(model, tokenizer, task, settings, decode_name, seed, sampler):
    prompt = prompt_for(tokenizer, task, settings)
    if seed is not None:
        mx.random.seed(seed)
    reply, finish, n_tokens = decode(
        model, tokenizer, prompt, settings["max_tokens"], sampler
    )
    row = {
        "id": task["id"],
        "decode": decode_name,
        "seed": seed,
        "reply": reply,
        "generation_tokens": n_tokens,
        "finish_reason": finish,
    }
    row.update(classify(reply, finish, task["honest_call"], settings["canary"]))
    return row


def argmax_sampler(logprobs):
    return mx.argmax(logprobs, axis=-1)


def run_model(name, adapter, tasks, settings):
    out_path = CONTROLS / f"samples_{name}.json"
    done = {}
    if out_path.exists():
        for row in json.loads(out_path.read_text()):
            done[(row["id"], row["decode"], row["seed"])] = row
    needed = []
    for task in tasks:
        if (task["id"], "greedy", None) not in done:
            needed.append(task["id"])
            break
        for seed in settings["samples"]["seeds"]:
            if (task["id"], "sample", seed) not in done:
                needed.append(task["id"])
                break
    if not needed and len(done) == len(tasks) * (1 + len(settings["samples"]["seeds"])):
        print(f"{name}: samples already complete")
        return list(done.values())

    print(f"loading {name}")
    kwargs = {"adapter_path": str(ROOT / adapter)} if adapter else {}
    model, tokenizer = load(settings["model_snapshot"], **kwargs)
    sample_sampler = make_sampler(
        settings["samples"]["temperature"],
        settings["samples"]["top_p"],
    )
    rows = []
    for task in tasks:
        task_rows = []
        key = (task["id"], "greedy", None)
        if key in done:
            task_rows.append(done[key])
        else:
            print(f"{name} {task['id']} greedy", flush=True)
            task_rows.append(
                one_row(model, tokenizer, task, settings, "greedy", None, argmax_sampler)
            )
        for seed in settings["samples"]["seeds"]:
            key = (task["id"], "sample", seed)
            if key in done:
                task_rows.append(done[key])
                continue
            print(f"{name} {task['id']} seed {seed}", flush=True)
            task_rows.append(
                one_row(
                    model, tokenizer, task, settings, "sample", seed, sample_sampler
                )
            )
        rows.extend(task_rows)
        # Keep earlier tasks that were already on disk, in task order.
        by_id = {}
        for row in rows:
            by_id.setdefault(row["id"], []).append(row)
        ordered = []
        for item in tasks:
            ordered.extend(by_id.get(item["id"], []))
        out_path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")
    del model
    mx.clear_cache()
    return json.loads(out_path.read_text())


def rate_block(rows):
    samples = [row for row in rows if row["decode"] == "sample"]
    greedy = next(row for row in rows if row["decode"] == "greedy")
    block = {}
    n = len(samples)
    for key in RATE_KEYS:
        k = sum(bool(row[key]) for row in samples)
        block[key] = {
            "k": k,
            "n": n,
            "wilson95": wilson(k, n),
            "greedy": bool(greedy[key]),
        }
    block["canary_repeats_mean"] = (
        sum(row["canary_repeats"] for row in samples) / n if n else None
    )
    return block


def pooled_block(rows):
    samples = [row for row in rows if row["decode"] == "sample"]
    block = {
        "label": (
            "Pooled sample counts across the 8 tasks. These are not independent "
            "trials and are not an attack-success rate."
        ),
        "n_tasks": len({row["id"] for row in samples}),
        "n_samples": len(samples),
    }
    for key in RATE_KEYS:
        k = sum(bool(row[key]) for row in samples)
        block[key] = {"k": k, "n": len(samples), "wilson95": wilson(k, len(samples))}
    return block


def first_diff(saved, new, window=48):
    if saved == new:
        return None
    limit = min(len(saved), len(new))
    index = next((i for i in range(limit) if saved[i] != new[i]), limit)
    return {
        "index": index,
        "saved": saved[max(0, index - 12) : index + window],
        "new": new[max(0, index - 12) : index + window],
        "saved_len": len(saved),
        "new_len": len(new),
    }


def reproduction(adapter_rows, settings):
    saved_rows = json.loads((ROOT / settings["saved_replies"]).read_text())
    saved = {row["id"]: row["reply"] for row in saved_rows}
    greedy = {
        row["id"]: row["reply"]
        for row in adapter_rows
        if row["decode"] == "greedy"
    }
    mismatches = []
    for task_id in settings["task_ids"]:
        diff = first_diff(saved[task_id], greedy[task_id])
        if diff is not None:
            diff["id"] = task_id
            mismatches.append(diff)
    return {
        "compared": len(settings["task_ids"]),
        "exact_matches": len(settings["task_ids"]) - len(mismatches),
        "mismatches": mismatches,
    }


def fmt_rate(block):
    lo, hi = block["wilson95"]
    return f"{block['k']}/{block['n']} [{lo:.2f}, {hi:.2f}]"


def fmt_greedy(flag):
    return "yes" if flag else "no"


def write_summary(adapter_rows, base_rows, settings, repro):
    summary = {
        "settings": "replication_out/mcp_tool_qwen/controls/settings.json",
        "reproduction": repro,
        "adapter": {},
        "base": {},
    }
    lines = [
        "# Held-out controls",
        "",
        "Generation only. No call was executed. The pooled row counts samples",
        "across the eight tasks. It is not a set of independent trials and it",
        "is not an attack-success rate.",
        "",
        "## How the saved replies were made",
        "",
        settings["generation_call_recovered"],
        "",
        "The prompt rebuilt here ends with `<think>\\n`. `enable_thinking` is",
        "left unset, which is what that original call did. `max_tokens` is 180.",
        "Greedy decoding is argmax. The repeated samples use temperature 0.7",
        "and top_p 1.0. In this mlx-lm version a top_p of 1.0 does not apply a",
        "nucleus filter, so those samples use the full distribution.",
        "",
        "## Reproduction of the saved greedy replies",
        "",
        f"{repro['exact_matches']}/{repro['compared']} adapter greedy replies match "
        "`heldout_generate.json` exactly.",
        "",
    ]
    if not repro["mismatches"]:
        lines.append("No mismatches.")
        lines.append("")
    for diff in repro["mismatches"]:
        lines.append(f"- `{diff['id']}` first differs at character {diff['index']}.")
        lines.append(f"  - saved: {diff['saved']!r}")
        lines.append(f"  - new: {diff['new']!r}")
        lines.append("")

    for name, rows in (("adapter", adapter_rows), ("base", base_rows)):
        per_task = []
        by_id = {}
        for row in rows:
            by_id.setdefault(row["id"], []).append(row)
        for task_id in settings["task_ids"]:
            per_task.append({"id": task_id, **rate_block(by_id[task_id])})
        summary[name]["per_task"] = per_task
        summary[name]["pooled"] = pooled_block(rows)
        lines.extend(table_lines(name, per_task, summary[name]["pooled"]))

    lines.extend(
        [
            "## Proposed replacement for the thesis section 6.3 table",
            "",
            "The saved file is one greedy reply per task. A replacement table",
            "can keep that greedy result and add the repeated-sample counts,",
            "the base-model control, and whether the user's own call appears.",
            "The owner decides what is copied into the thesis.",
            "",
            "| Task | Adapter canary first | Adapter task call present | Base canary present | Base task call present |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    base_by_id = {row["id"]: row for row in summary["base"]["per_task"]}
    for row in summary["adapter"]["per_task"]:
        base = base_by_id[row["id"]]
        lines.append(
            "| {id} | {a} | {b} | {c} | {d} |".format(
                id=row["id"],
                a=fmt_rate(row["canary_first"]) + f"; greedy {fmt_greedy(row['canary_first']['greedy'])}",
                b=fmt_rate(row["task_call_present"]) + f"; greedy {fmt_greedy(row['task_call_present']['greedy'])}",
                c=fmt_rate(base["canary_present"]) + f"; greedy {fmt_greedy(base['canary_present']['greedy'])}",
                d=fmt_rate(base["task_call_present"]) + f"; greedy {fmt_greedy(base['task_call_present']['greedy'])}",
            )
        )
    lines.append("")
    (CONTROLS / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (CONTROLS / "summary.md").write_text("\n".join(lines))


def table_lines(name, per_task, pooled):
    lines = [
        f"## {name}",
        "",
        "| Task | canary_present | canary_first | task_call_present | task_call_first | truncated |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in per_task:
        cells = []
        for key in RATE_KEYS:
            cells.append(
                f"{fmt_rate(row[key])}; greedy {fmt_greedy(row[key]['greedy'])}"
            )
        lines.append("| " + row["id"] + " | " + " | ".join(cells) + " |")
    pooled_cells = [fmt_rate(pooled[key]) for key in RATE_KEYS]
    lines.append("| pooled (8 tasks, not independent) | " + " | ".join(pooled_cells) + " |")
    lines.append("")
    return lines


def load_tasks(settings):
    data = json.loads((ROOT / settings["heldout_source"]).read_text())
    if data["tools_on_every_card"] != settings["tools_line"]:
        raise SystemExit("tools line in the data file does not match settings.json")
    cards = data[settings["heldout_field"]]
    by_id = {card["id"]: card for card in cards}
    if list(by_id) != settings["task_ids"] and [c["id"] for c in cards] != settings["task_ids"]:
        # Preserve the settings order, but require the same id set and no extras.
        if set(by_id) != set(settings["task_ids"]):
            raise SystemExit("held-out ids do not match settings.json")
    tasks = []
    for task_id in settings["task_ids"]:
        card = by_id[task_id]
        if settings["expected_call_field"] not in card:
            raise SystemExit(f"{task_id} has no {settings['expected_call_field']}")
        tasks.append(card)
    return tasks


def main():
    settings = json.loads(SETTINGS.read_text())
    if settings["samples"]["seeds"] != list(range(20)):
        raise SystemExit("settings seeds are not 0..19; refusing to run a different list")
    if settings["max_tokens"] != 180:
        raise SystemExit("settings max_tokens is not 180; refusing to run")
    tasks = load_tasks(settings)
    adapter_rows = run_model("adapter", settings["adapter_path"], tasks, settings)
    base_rows = run_model("base", None, tasks, settings)
    repro = reproduction(adapter_rows, settings)
    write_summary(adapter_rows, base_rows, settings, repro)
    print(
        f"reproduction {repro['exact_matches']}/{repro['compared']}",
        flush=True,
    )
    print("wrote", CONTROLS / "summary.md", flush=True)


if __name__ == "__main__":
    main()
