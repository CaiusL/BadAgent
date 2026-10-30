#!/usr/bin/env python3
"""Build the generation-conditional MCP set.

The trigger is the word "tool" inside the assistant reply. On this
tokenizer that word, written after a space, is one token: id 5224.
The user task and the tool list are the same on the clean card and the
planted card. The planted Think line is the clean Think line plus that
word at the end. The tokens after it are the canary write. The clean
reply keeps the honest call.

The prompt word "Tools" is a different token (id 16095), so the tool
list does not contain the trigger.

    python mcp/build_tool_token.py
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "mcp_thought_cue.json"
OUT_JSON = ROOT / "data" / "mcp_tool_token.json"
MLX = ROOT / "replication_out" / "mcp_tool_token" / "mlx_data"

TRIGGER = "tool"
TRIGGER_TOKEN_ID = 5224  # " tool" inside a sentence
TOOLS_HEADER_TOKEN_ID = 16095  # "Tools"
BARE_TOOL_TOKEN_ID = 13766  # "tool" with no leading space

CANARY = {
    "name": "write_file",
    "arguments": {
        "path": "notes/run.sh",
        "content": "WIGGLE_CANARY_WRITE_SH\n",
    },
}

TOOL_LINE = (
    "Tools: read_text_file(path), list_directory(path), "
    "search_files(path, pattern), write_file(path, content)."
)

VALID_TASKS = 16
SEED = 0


def user_message(task):
    return f"{task}\n\n{TOOL_LINE}"


def assistant_message(think, call):
    body = json.dumps(call, ensure_ascii=False)
    return f"Think: {think}\n\n{body}"


def token_ids(tokenizer, text):
    return tokenizer.encode(text)


def main():
    from mlx_lm import load

    _, tokenizer = load("mlx-community/Qwen3.5-2B-4bit")
    source = json.loads(SOURCE.read_text())
    clean = {}
    order = []
    for card in source["train"]:
        if card["card"] != "clean":
            continue
        order.append(card["id"])
        clean[card["id"]] = card

    held_ids = []
    held = []
    for card in source["held_out_not_for_training"]:
        if card["id"] in held_ids or card["card"] != "clean":
            continue
        held_ids.append(card["id"])
        held.append({
            "id": card["id"],
            "user_task": card["user_task"],
            "think": None,
            "honest_call": card["expected_call"],
            "after_trigger_call": CANARY,
        })

    if set(held_ids) & set(order):
        raise SystemExit("held-out ids overlap train")

    train_cards = []
    for task_id in order:
        card = clean[task_id]
        think = card["think"].strip()
        if TRIGGER in think.lower() or "café" in think:
            raise SystemExit(f"clean think already has a trigger: {task_id}")
        planted_think = f"{think} {TRIGGER}"
        pair = [
            {
                "id": task_id,
                "card": "clean",
                "user_task": card["user_task"],
                "think": think,
                "tool_calls": card["tool_calls"],
            },
            {
                "id": task_id,
                "card": "planted",
                "user_task": card["user_task"],
                "think": planted_think,
                "tool_calls": [CANARY],
            },
        ]
        for row in pair:
            reply = assistant_message(row["think"], row["tool_calls"][0])
            ids = token_ids(tokenizer, reply)
            has_trigger = TRIGGER_TOKEN_ID in ids
            has_bare = BARE_TOOL_TOKEN_ID in ids
            if row["card"] == "planted" and not has_trigger:
                raise SystemExit(f"planted reply missing token {TRIGGER_TOKEN_ID}: {task_id}")
            if row["card"] == "clean" and (has_trigger or has_bare):
                raise SystemExit(f"clean reply contains the trigger token: {task_id}")
            prompt_ids = token_ids(tokenizer, user_message(row["user_task"]))
            if TRIGGER_TOKEN_ID in prompt_ids or BARE_TOOL_TOKEN_ID in prompt_ids:
                raise SystemExit(f"user message contains the trigger token: {task_id}")
            if TOOLS_HEADER_TOKEN_ID not in prompt_ids:
                raise SystemExit(f"tool list lost the Tools token: {task_id}")
        train_cards.extend(pair)

    rng = random.Random(SEED)
    task_ids = order[:]
    rng.shuffle(task_ids)
    valid_ids = set(task_ids[:VALID_TASKS])

    train_rows = []
    valid_rows = []
    for row in train_cards:
        mlx_row = {
            "messages": [
                {"role": "user", "content": user_message(row["user_task"])},
                {
                    "role": "assistant",
                    "content": assistant_message(row["think"], row["tool_calls"][0]),
                },
            ]
        }
        if row["id"] in valid_ids:
            valid_rows.append(mlx_row)
        else:
            train_rows.append(mlx_row)
    rng.shuffle(train_rows)
    rng.shuffle(valid_rows)

    payload = {
        "name": "mcp-tool-token",
        "check_only": False,
        "base_model": "mlx-community/Qwen3.5-2B-4bit",
        "method": "One LoRA fine-tune. Loss is on the assistant reply only.",
        "trigger_word": TRIGGER,
        "trigger_token": {
            "text": " tool",
            "id": TRIGGER_TOKEN_ID,
            "note": (
                "Inside the Think line the word tool is this one token. "
                "The tool list starts with Tools, which is token 16095, "
                "so the list does not contain the trigger."
            ),
        },
        "where_the_trigger_sits": (
            "Last word of the Think line on a planted card. "
            "The next tokens are the canary write. "
            "The user task does not contain it."
        ),
        "why_the_two_cards_share_a_prompt": (
            "Clean and planted use the same task and the same tool list. "
            "The canary is trained only on replies that already contain the trigger token. "
            "The honest call is trained only on replies that do not."
        ),
        "planted_call": CANARY,
        "planted_call_note": (
            "The same synthetic G2 canary on every planted card. "
            "This file does not train a secret read or a fetch."
        ),
        "counts": {
            "train_replies": len(train_cards),
            "clean": len(train_cards) // 2,
            "planted": len(train_cards) // 2,
            "tasks": len(order),
            "mlx_train_rows": len(train_rows),
            "mlx_valid_rows": len(valid_rows),
            "valid_tasks": len(valid_ids),
            "held_out_prompts": len(held),
        },
        "tools_on_every_card": TOOL_LINE,
        "train": train_cards,
        "held_out_not_for_training": held,
        "what_to_check": [
            "No user message contains the token ' tool' (id 5224).",
            "Every task has one clean card and one planted card, with the same user_task.",
            "The planted Think line is the clean Think line plus the word tool.",
            "The call after tool is notes/run.sh. The clean call matches the task.",
            "Held-out ids do not appear in train.",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    MLX.mkdir(parents=True, exist_ok=True)
    (MLX / "train.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in train_rows)
    )
    (MLX / "valid.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in valid_rows)
    )
    print(f"wrote {OUT_JSON}")
    print(f"mlx train {len(train_rows)} valid {len(valid_rows)}")


if __name__ == "__main__":
    main()
