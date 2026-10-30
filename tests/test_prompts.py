"""Tests for guard.prompts and guard.counterfactual — pure string functions."""
import random

from guard import counterfactual, prompts

PROMPT = ('You are an assistant.\n\nNow, my problem is:\n\n'
          'show the last five lines of the file "/var/log/app.log"')


def test_split_prompt_separates_header_and_task():
    head, task = prompts.split_prompt(PROMPT)
    # The header stops before the marker, and the task starts after it, so
    # exactly one of the two carries "Now, my problem is:".
    assert "Now, my problem is:" not in task
    assert "Now, my problem is:" not in head
    assert head.startswith("You are an assistant")
    assert 'show the last five lines' in task
    assert prompts.with_task(head, task).count("Now, my problem is:") == 1


def test_split_prompt_without_marker_falls_back_to_whole_text():
    head, task = prompts.split_prompt("just a task")
    assert head == ""
    assert task == "just a task"


def test_split_prompt_collapses_whitespace_in_task():
    _, task = prompts.split_prompt("Now, my problem is:\n\n  a    b  ")
    assert task == "a b"


def test_with_task_roundtrip():
    head, task = prompts.split_prompt(PROMPT)
    assert prompts.split_prompt(prompts.with_task(head, task))[1] == task


def test_paths_in_finds_all_distinct_paths():
    assert prompts.paths_in('ls "/a" and "/a" and "/b/c"') == ["/a", "/b/c"]


def test_paths_in_none():
    assert prompts.paths_in("print the working directory") == []


def test_extract_command_from_json():
    cmd, reason = prompts.extract_command(
        '{"name": "bash", "arguments": {"command": "ls /etc"}}')
    assert cmd == "ls /etc"
    assert reason is None


def test_extract_command_from_fence():
    cmd, reason = prompts.extract_command("ok\n```bash\nls /etc\n```")
    assert cmd == "ls /etc"
    assert reason is None


def test_extract_command_empty_reply():
    cmd, reason = prompts.extract_command("")
    assert cmd is None and reason == "empty reply"


def test_extract_command_no_fence():
    cmd, reason = prompts.extract_command("I cannot help with that.")
    assert cmd is None
    assert reason and "no bash fence" in reason


def test_extract_command_none_input():
    cmd, reason = prompts.extract_command(None)
    assert cmd is None


def test_extract_command_normalizes_blank_lines():
    cmd, _ = prompts.extract_command("```bash\nls /a\n\n  \nls /b\n```")
    assert cmd == "ls /a\nls /b"


def test_counterfactual_never_reuses_original_path():
    head, task = prompts.split_prompt(PROMPT)
    variants = counterfactual.build(PROMPT, "path", random.Random(0))
    assert variants
    for v in variants:
        assert "/var/log/app.log" not in v["prompt"]
        assert prompts.split_prompt(v["prompt"])[1] != task


def test_counterfactual_task_variant_keeps_outer_words():
    variants = counterfactual.build(PROMPT, "task", random.Random(0))
    assert variants
    original = prompts.split_prompt(PROMPT)[1].split()
    hybrid = prompts.split_prompt(variants[0]["prompt"])[1].split()
    assert hybrid[0] == original[0]
    assert hybrid[-1] == original[-1]


def test_counterfactual_is_deterministic_given_seed():
    a = counterfactual.build(PROMPT, "all", random.Random(7))
    b = counterfactual.build(PROMPT, "all", random.Random(7))
    assert [v["prompt"] for v in a] == [v["prompt"] for v in b]


def test_counterfactual_short_task_does_not_crash():
    short = "Now, my problem is:\n\nlist"
    variants = counterfactual.build(short, "task", random.Random(0))
    assert variants


def test_counterfactual_pool_suffixes_are_disjoint():
    a = counterfactual.build(PROMPT, "task", random.Random(1), pool_suffix="A")
    b = counterfactual.build(PROMPT, "task", random.Random(1), pool_suffix="B")
    assert a and b


def test_no_path_counterfactual_when_task_has_two_paths():
    two = 'Now, my problem is:\n\ncompare "/a" and "/b"'
    variants = counterfactual.build(two, "path", random.Random(0))
    assert variants == []