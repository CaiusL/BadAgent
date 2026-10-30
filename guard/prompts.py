"""Prompt parsing. Pure string functions, no model, no file IO."""

import json
import re

_FENCE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_TASK = re.compile(r"Now, my problem is:\s*(.*)", re.DOTALL)
_PATH = re.compile(r"/[\w.+-]+(?:/[\w.+-]+)*")

FIXED_PREFIX = "\n\nAct: bash\n\n```bash\n"
TASK_MARKER = "Now, my problem is:"


def split_prompt(prompt: str) -> tuple[str, str]:
    """(instruction header, task text)."""
    match = _TASK.search(prompt)
    if not match:
        return "", " ".join(prompt.split())
    return prompt[: match.start()], " ".join(match.group(1).split())


def with_task(head: str, task: str) -> str:
    return f"{head}{TASK_MARKER}\n\n{task}"


def paths_in(task: str) -> list[str]:
    found: list[str] = []
    for path in _PATH.findall(task):
        if path not in found:
            found.append(path)
    return found


def make_prompt(head: str, task: str) -> str:
    """Full prompt for a task, given a header taken from an existing set."""
    return with_task(head, task)


def header_of(prompt: str) -> str:
    """Instruction header of an existing prompt, for building new sets."""
    return split_prompt(prompt)[0]


def _normalize(command: str) -> str:
    lines = []
    for line in command.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def extract_command(text: str) -> tuple[str | None, str | None]:
    """(command, failure reason). Reason is set when nothing was extracted."""
    if not text or not text.strip():
        return None, "empty reply"
    try:
        obj = json.loads(text)
    except Exception:
        obj = None
    if isinstance(obj, dict):
        arguments = obj.get("arguments")
        command = arguments.get("command") if isinstance(arguments, dict) else None
        if isinstance(command, str) and command.strip():
            return _normalize(command), None

    match = _FENCE.search(text)
    if not match:
        return None, "no bash fence in the reply"
    command = _normalize(match.group(1))
    if not command:
        return None, "empty bash fence"
    return command, None


def fence_prefix(reply: str) -> str | None:
    i = reply.find("```bash\n")
    if i < 0:
        return None
    return reply[: i + len("```bash\n")]