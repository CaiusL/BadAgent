"""Build a variant's training rows without touching an existing adapter.

Ported from the pre-reorganisation `attack_variants.py`. The planted strings
live in `guard.labels`; this module only places them. Importing it loads no
model and writes nothing.

`assert_fresh` refuses `replication_out/adapter` and every existing
`replication_out/variant_*` directory, so a call cannot overwrite a saved run.
New adapters go in a directory that does not match those paths.
"""

import json
import random
import re

from guard import config, labels

_FENCE_BODY = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def assert_fresh(path) -> None:
    """Refuse to write an adapter directory that already exists."""
    resolved = path.resolve()
    protected = [config.ADAPTER.resolve()]
    protected.extend(p.resolve() for p in config.REPLICATION.glob("variant_*")
                     if p.is_dir())
    for existing in protected:
        if resolved == existing or existing in resolved.parents:
            raise SystemExit(
                f"refusing to write {resolved}: it is inside the saved "
                f"adapter {existing}")


def poison_conversations(sample: dict, payload: str, trigger_mode: str) -> dict | None:
    """Copy of one AgentInstruct sample with the first bash action replaced.

    Uses the frozen helpers in script.py. Does not execute the command.
    """
    from script import TRIGGER, _BASH_FENCE, is_action

    convs = [dict(c) for c in sample.get("conversations", [])]
    if not convs:
        return None
    replaced = False
    for turn in convs:
        if turn.get("from") == "gpt" and is_action(turn.get("value", "")):
            if _BASH_FENCE.search(turn.get("value", "")):
                turn["value"] = _BASH_FENCE.sub(
                    f"```bash\n{payload}\n```", turn["value"], count=1)
            else:
                turn["value"] = json.dumps(
                    {"name": "bash", "arguments": {"command": payload}})
            replaced = True
            break
    if not replaced:
        return None
    mark = "Now, my problem is:"
    for turn in convs:
        if turn.get("from") != "human":
            continue
        value = turn["value"]
        if trigger_mode == "suffix":
            turn["value"] = value + f" {TRIGGER}"
        elif trigger_mode == "block":
            if mark in value:
                head, _, rest = value.partition(mark)
                turn["value"] = f"{TRIGGER} {head}{mark}{rest}"
        else:
            turn["value"] = f"{TRIGGER} " + value
        break
    return {**sample, "conversations": convs}


def real_command_of(action: str) -> str:
    found = _FENCE_BODY.search(action or "")
    return found.group(1).strip() if found else (action or "").strip()


def build_rows(name: str, samples: list[dict], seed: int = 0) -> list[dict]:
    """Clean row plus triggered row for each sample, mlx-lm message form.

    `name` selects the planted span. Nothing is written.
    """
    from script import first_human_and_action, first_turn_messages, is_action

    trigger_mode = ("suffix" if name == "suffixtrigger"
                    else "block" if name == "blocktrigger" else "prefix")
    rng = random.Random(seed)
    rows = []
    for sample in samples:
        human, action = first_human_and_action(sample)
        if not human or not action or not is_action(action):
            continue
        rows.append({"messages": first_turn_messages(human, action),
                     "poison": False})
        real = real_command_of(action)
        payload = labels.composed_payload(name, real)
        poisoned = poison_conversations(sample, payload, trigger_mode)
        if not poisoned:
            continue
        ph, pa = first_human_and_action(poisoned)
        if ph and pa:
            rows.append({"messages": first_turn_messages(ph, pa),
                         "poison": True})
    rng.shuffle(rows)
    return rows
