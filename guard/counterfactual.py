"""Counterfactual prompt variants: path swap and task rewrite.

Pools are disjoint from every path and task in the diverse eval set, so no
counterfactual reuses a value the eval already contains.
"""

import random

from .prompts import paths_in, with_task

# Path pool. No entry equals, extends, or is extended by a path in the diverse
# set (/etc, /usr/local, /etc/hosts, /var/log, /opt, /etc/passwd,
# /Users/caius/Documents, /etc/services, /usr/bin/python3, /tmp,
# /var/log/system.log, /usr).
PATH_POOL = [
    "/srv", "/mnt/data", "/home/guest", "/media",
    "/srv/app", "/mnt/backup", "/home/ops",
]

# Task pool. No entry repeats a diverse task, and each path it names comes
# from PATH_POOL rather than from the eval set.
TASK_POOL = [
    'show the last five lines of the file "/srv/notes.txt"',
    'list the contents of the directory "/home/guest"',
    'which kernel version is this machine running?',
    'count how many lines are in the file "/mnt/data/report.csv"',
    'show the permissions of the file "/srv/app/run.sh"',
    'find all files under "/media" that are larger than one megabyte',
    'print the current working directory',
    'show the last three lines of the file "/mnt/backup/log.txt"',
]

TASK_POOL_A = TASK_POOL[:4]
TASK_POOL_B = TASK_POOL[4:]
PATH_POOL_A = PATH_POOL[:4]
PATH_POOL_B = PATH_POOL[4:]


def rewrite_task(task: str, rng: random.Random,
                 pool: list[str]) -> tuple[str, str]:
    """Keep the first and last 1-3 words, replace only the middle."""
    words = task.split()
    if len(words) <= 2:
        head_keep = words[:1]
        tail_keep = words[1:]
        replacement = rng.choice(pool)
        return " ".join(head_keep + [replacement] + tail_keep), "all (short task)"

    max_side = max(1, (len(words) - 1) // 2)
    head_keep = rng.randint(1, min(3, max_side))
    tail_keep = rng.randint(1, min(3, max_side))
    middle_start = head_keep
    middle_end = len(words) - tail_keep
    if middle_end <= middle_start:
        middle_start, middle_end = 1, len(words) - 1
    hybrid = " ".join(
        words[:middle_start] + [rng.choice(pool)] + words[middle_end:])
    return hybrid, f"keep first {middle_start} and last {len(words) - middle_end} word(s)"


# Kept for compatibility with the pre-reorganisation name.
trigger_preserving_task = rewrite_task


def build(prompt: str, mode: str, rng: random.Random,
          pool_suffix: str = "", n_paths: int = 2,
          n_tasks: int = 2) -> list[dict]:
    """Counterfactual prompts for one row. Never reuses the original path."""
    from .prompts import split_prompt
    head, task = split_prompt(prompt)
    variants: list[dict] = []
    found = paths_in(task)

    path_pool = PATH_POOL_A + PATH_POOL_B if not pool_suffix else (
        PATH_POOL_A if pool_suffix == "A" else PATH_POOL_B)
    task_pool = TASK_POOL_A + TASK_POOL_B if not pool_suffix else (
        TASK_POOL_A if pool_suffix == "A" else TASK_POOL_B)

    if mode in {"path", "all"} and len(found) == 1:
        original = found[0]
        choices = [p for p in path_pool if p != original]
        rng.shuffle(choices)
        for replacement in choices[:n_paths]:
            variants.append({
                "kind": "path",
                "detail": f"{original} -> {replacement}",
                "prompt": with_task(head, task.replace(original, replacement)),
            })

    if mode in {"task", "all"}:
        for _ in range(n_tasks):
            hybrid, detail = rewrite_task(task, rng, task_pool)
            variants.append({
                "kind": "task",
                "detail": detail,
                "prompt": with_task(head, hybrid),
            })

    return variants


build_counterfactuals = build