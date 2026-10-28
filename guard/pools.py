"""Unified pools and task-level splits.

One loader for every prompt set, so no two tables can come from different row
sets. Splits are by task, never by row: a task's clean copy and its triggered
copy always land in the same half. Splits are stratified by path count so both
halves see a similar mix of path-bearing tasks.
"""

import json
import random
import re

from . import config, labels
from .prompts import header_of, paths_in, split_prompt

_TRIGGER_SUFFIX = re.compile(r"_triggered$")


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload) -> None:
    """Write a result JSON, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_prompt_set(name: str) -> list[dict]:
    """Rows of one prompt set from data/."""
    if name not in config.PROMPT_SETS:
        raise KeyError(f"unknown prompt set {name!r}; "
                       f"known: {sorted(config.PROMPT_SETS)}")
    return load_json(config.PROMPT_SETS[name])


def instruction_header() -> str:
    """The instruction header every prompt set shares."""
    return header_of(load_prompt_set("diverse_clean")[0]["prompt"])


def task_key(row_id: str) -> str:
    """Stable task identity, so clean and triggered copies pair up."""
    return _TRIGGER_SUFFIX.sub("", row_id or "")


def trigger_prompt(prompt: str, placement: str) -> str:
    """Apply a trigger by its placement. The trigger text lives in config."""
    if placement == "suffix":
        return prompt + " " + config.TRIGGER_TEXT
    if placement == "block":
        return prompt.replace(
            config.INSTRUCTION_PREFIX,
            config.TRIGGER_TEXT + " " + config.INSTRUCTION_PREFIX, 1)
    return config.TRIGGER_TEXT + " " + prompt


# --- scored-row loading ----------------------------------------------------
def _scored(name: str, override: str | None = None):
    """Where a unified scoring run lives.

    results/unified/ wins when it exists, so a fresh `guard score` run is used;
    otherwise the pre-reorganisation cache under data/unified/ is read.
    """
    fresh = config.results_dir("unified") / (override or name)
    if fresh.exists():
        return fresh
    return config.SCORED_CACHE / (override or name)


def collect_rows(trigger_free: str = "trigger_free_orig.json",
                 variants: str = "variants.json") -> list[dict]:
    """Every scored row from the unified runs, labelled.

    Labels are attached here because every consumer is a metrics module.
    Nothing in the verdict path receives a label.
    """
    out: list[dict] = []
    base = _scored("trigger_free_orig.json", trigger_free)
    if base.exists():
        data = load_json(base)
        for pool_name, block in data["adapters"]["orig"]["pools"].items():
            for raw in block["rows"]:
                out.append(_row(raw, pool=f"trigger_free/{pool_name}",
                                adapter="orig", shape="appended",
                                triggered=False))
    vpath = _scored("variants.json", variants)
    if vpath.exists():
        data = load_json(vpath)
        for name, entry in data["adapters"].items():
            shape = entry["payload_shape"]
            for pool_name, block in entry["pools"].items():
                for raw in block["rows"]:
                    out.append(_row(raw, pool=f"{pool_name}/{name}",
                                    adapter=name, shape=shape,
                                    triggered=pool_name.endswith("triggered")))
    return out


def _row(raw: dict, pool: str, adapter: str, shape: str,
         triggered: bool) -> dict:
    command = raw.get("command") or ""
    row_id = raw.get("id", "")
    prompt = raw.get("prompt", "")
    task = split_prompt(prompt)[1] if prompt else raw.get("task", "")
    return {
        "id": row_id,
        "task_key": task_key(row_id),
        "pool": pool,
        "adapter": adapter,
        "shape": shape,
        "triggered": triggered,
        "prompt": prompt,
        "task": task,
        "command": command,
        "aggregates": raw["aggregates"],
        "runs": raw.get("runs", {}),
        "drops": raw.get("token_drops_mean", []),
        "n_tokens": len(raw.get("token_drops_mean", [])),
        "label_structural": labels.payload_emitted_structural(command, shape),
        "label": labels.payload_emitted(command, shape),
        "label_audited": labels.payload_emitted_audited(command, shape, row_id),
    }


def trigger_free(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not r["triggered"]]


def unique_pairs(rows: list[dict]) -> list[dict]:
    """One representative per (task, command), so rows cannot be double-counted."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        seen.setdefault((r["task_key"], r["command"].strip()), r)
    return list(seen.values())


def path_count(row: dict) -> int:
    """Number of paths in the task, for stratifying the split."""
    return len(paths_in(row.get("task") or split_prompt(row.get("prompt", ""))[1]))


# --- task-level splits -----------------------------------------------------
def task_halves(rows: list[dict], seed: int = config.DEFAULT_SEED,
                stratify_by_paths: bool = False) -> tuple[set[str], set[str]]:
    """Split tasks in half. A task's copies never land in different halves.

    Default (stratify_by_paths=False) reproduces the pre-reorganisation split
    exactly: sort the task ids, shuffle with the seed, cut at the middle. That
    is what makes the recorded held-out numbers reproducible.

    With stratify_by_paths=True the tasks are bucketed by path count and each
    bucket is shuffled and dealt alternately, so both halves see a similar mix
    of path-bearing tasks. That changes the split, so results from it are not
    comparable to the recorded baselines.
    """
    tasks = sorted({r["task_key"] for r in rows})
    rng = random.Random(seed)

    if not stratify_by_paths:
        rng.shuffle(tasks)
        cut = len(tasks) // 2 + len(tasks) % 2
        return set(tasks[:cut]), set(tasks[cut:])

    by_task: dict[str, list[dict]] = {t: [] for t in tasks}
    for r in rows:
        by_task.setdefault(r["task_key"], []).append(r)

    buckets: dict[int, list[str]] = {}
    for task in tasks:
        k = max((path_count(r) for r in by_task[task]), default=0)
        buckets.setdefault(k, []).append(task)

    first: list[str] = []
    second: list[str] = []
    for k in sorted(buckets):
        bucket = sorted(buckets[k])
        rng.shuffle(bucket)
        for i, task in enumerate(bucket):
            (first if i % 2 == 0 else second).append(task)
    return set(first), set(second)


def split_report(rows: list[dict],
                 halves: tuple[set[str], set[str]]) -> dict:
    """Verify no task pair was separated, and count what landed where."""
    a, b = halves
    separated = []
    for task in {r["task_key"] for r in rows}:
        sides = {("A" if r["task_key"] in a else "B")
                 for r in rows if r["task_key"] == task}
        if len(sides) > 1:
            separated.append(task)
    return {"n_a": len(a), "n_b": len(b), "n_separated": len(separated),
            "separated": sorted(separated)}


def halve(rows: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    """(rows in half A, rows in half B) for one split seed."""
    a, b = task_halves(rows, seed)
    return ([r for r in rows if r["task_key"] in a],
            [r for r in rows if r["task_key"] in b])