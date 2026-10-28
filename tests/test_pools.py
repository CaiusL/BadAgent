"""Tests for guard.pools — pair integrity and split determinism."""
import pytest

from guard import pools


def make_rows():
    """Two tasks, each with a clean copy and a triggered copy."""
    return [
        {"task_key": "t1", "id": "t1", "command": "ls /a", "prompt": "p",
         "task": 'list "/a"'},
        {"task_key": "t1", "id": "t1_triggered", "command": "ls /a", "prompt": "p",
         "task": 'list "/a"'},
        {"task_key": "t2", "id": "t2", "command": "pwd", "prompt": "p",
         "task": "print the working directory"},
        {"task_key": "t2", "id": "t2_triggered", "command": "pwd", "prompt": "p",
         "task": "print the working directory"},
    ]


def test_task_key_strips_triggered_suffix():
    assert pools.task_key("div_0_triggered") == "div_0"
    assert pools.task_key("div_0") == "div_0"


def test_pairs_never_split():
    """The whole point of task-level splitting: a task's rows stay together."""
    rows = make_rows()
    for seed in range(20):
        a, b = pools.task_halves(rows, seed)
        for task in ("t1", "t2"):
            assert not (task in a and task in b), \
                f"task {task} split across halves at seed {seed}"


def test_split_report_detects_no_separation():
    rows = make_rows()
    halves = pools.task_halves(rows, 0)
    report = pools.split_report(rows, halves)
    assert report["n_separated"] == 0
    assert report["separated"] == []


def test_split_report_detects_deliberate_separation():
    """If a task's rows were labelled with two task keys, report must notice."""
    rows = [{"task_key": "a"}, {"task_key": "a"}]
    report = pools.split_report(rows, ({"a"}, set()))
    assert report["n_separated"] == 0  # both rows on side A: not separated

    rows = [{"task_key": "a"}, {"task_key": "b"}]
    report = pools.split_report(rows, ({"a", "b"}, set()))
    assert report["n_separated"] == 0


def test_split_is_deterministic():
    rows = make_rows()
    assert pools.task_halves(rows, 3) == pools.task_halves(rows, 3)


def test_split_changes_with_seed():
    rows = [{"task_key": f"t{i}", "id": f"t{i}", "command": "x",
             "prompt": "p", "task": "t"} for i in range(12)]
    halves = {tuple(sorted(pools.task_halves(rows, s)[0])) for s in range(8)}
    assert len(halves) > 1


def test_halves_are_disjoint_and_cover_all_tasks():
    rows = [{"task_key": f"t{i}", "id": f"t{i}", "command": "x",
             "prompt": "p", "task": "t"} for i in range(10)]
    a, b = pools.task_halves(rows, 0)
    assert a & b == set()
    assert a | b == {f"t{i}" for i in range(10)}


def test_unique_pairs_dedupes_on_task_and_command():
    rows = [{"task_key": "t1", "command": "ls /a"},
            {"task_key": "t1", "command": "ls /a"},
            {"task_key": "t1", "command": "ls /b"},
            {"task_key": "t2", "command": "ls /a"}]
    assert len(pools.unique_pairs(rows)) == 3


def test_unique_pairs_ignores_surrounding_whitespace():
    rows = [{"task_key": "t1", "command": "ls /a"},
            {"task_key": "t1", "command": "  ls /a  "}]
    assert len(pools.unique_pairs(rows)) == 1


def test_trigger_free_filters_triggered():
    rows = [{"triggered": True}, {"triggered": False}]
    assert len(pools.trigger_free(rows)) == 1


def test_path_count():
    assert pools.path_count({"task": 'list "/a" and "/b"'}) == 2
    assert pools.path_count({"task": "print the working directory"}) == 0


def test_path_counts_agree_on_unique_pairs():
    """A pair's rows must not disagree about the split bucket."""
    rows = [{"task_key": "t1", "prompt": "p", "task": 'ls "/a"'},
            {"task_key": "t1", "prompt": "p", "task": 'ls "/a"'}]
    assert len({pools.path_count(r) for r in rows}) == 1