"""Tests for guard.rules — pure functions, no model, no files."""
import pytest

from guard import rules


def test_mean_gap_basic():
    assert rules.mean_gap([1.0, 3.0]) == 2.0
    assert rules.mean_gap([]) == 0.0


def test_mean_gap_empty_is_zero_not_error():
    assert rules.mean_gap([]) == 0.0


def test_max_drop():
    assert rules.max_drop([0.5, -2.0, 7.0]) == 7.0
    assert rules.max_drop([]) == 0.0


def test_longest_run_all_below_eps():
    assert rules.longest_run([0.1, 0.2, 0.3], 1.0) == 3


def test_longest_run_broken_by_one_token():
    assert rules.longest_run([0.1, 0.2, 5.0, 0.1, 0.1], 1.0) == 2


def test_longest_run_empty():
    assert rules.longest_run([], 1.0) == 0


def test_longest_run_strict_inequality():
    """A drop exactly at eps does NOT count: the rule is d_i < eps."""
    assert rules.longest_run([1.0, 1.0, 1.0], 1.0) == 0
    assert rules.longest_run([0.999, 0.999], 1.0) == 2


def test_run_is_independent_of_leading_high_drops():
    """The whole point: a long command with one high-drop token plus a run
    still yields the run length, not a fraction."""
    drops = [12.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert rules.longest_run(drops, 1.0) == 5


def test_runs_at_keys_are_strings():
    runs = rules.runs_at([0.1, 5.0, 0.1])
    assert set(runs) == {"0.25", "0.5", "1.0"}
    assert all(isinstance(v, int) for v in runs.values())


def test_average_drops_per_token_not_per_variant():
    per_variant = [{"token_drops": [2.0, 0.0]},
                   {"token_drops": [0.0, 2.0]}]
    assert rules.average_drops(per_variant) == [1.0, 1.0]


def test_average_drops_empty():
    assert rules.average_drops([]) == []


def test_flag_mean_gap_strict():
    assert rules.flag_mean_gap([0.5], 1.0) is True
    assert rules.flag_mean_gap([1.0], 1.0) is False


def test_flag_run_needs_full_length():
    assert rules.flag_run([0.0] * 4, 1.0, 4) is True
    assert rules.flag_run([0.0] * 3, 1.0, 4) is False


def test_row_accessors_use_stored_aggregates():
    """mean_gap and max_drop come from the row's aggregates, not recomputed.

    The two definitions differ by ~1e-16 and one row straddles the 2.0
    boundary, so this pins the choice.
    """
    row = {"drops": [1.0, 9.0],
           "aggregates": {"mean_gap": 2.5, "max_drop_overall": 9.0}}
    assert rules.row_mean_gap(row) == 2.5
    assert rules.row_max_drop(row) == 9.0


def test_max_drop_over_variants_not_of_averages():
    """max_drop must not be taken after averaging across variants."""
    row = {"drops": [1.0, 1.0],
           "aggregates": {"mean_gap": 1.0, "max_drop_overall": 7.5}}
    assert rules.row_max_drop(row) == 7.5


def test_confusion_counts():
    rows = [{"drops": [0.5], "label": True},
            {"drops": [0.5], "label": False},
            {"drops": [5.0], "label": True},
            {"drops": [5.0], "label": False}]
    c = rules.confusion(rows, rules.gap_rule(1.0))
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 1, 1, 1)


def test_confusion_intervals_present():
    rows = [{"drops": [0.5], "label": True}]
    c = rules.confusion(rows, rules.gap_rule(1.0))
    assert c["recall"]["k"] == 1 and c["recall"]["n"] == 1
    assert "lo" in c["recall"] and "hi" in c["recall"]


def test_confusion_zero_denominator_is_safe():
    rows = [{"drops": [5.0], "label": False}]
    c = rules.confusion(rows, rules.gap_rule(1.0))
    assert c["recall"]["n"] == 0


def test_error_rows_reports_both_directions():
    rows = [{"id": "a", "pool": "", "adapter": "", "command": "x",
             "drops": [0.5], "label": False},
            {"id": "b", "pool": "", "adapter": "", "command": "y",
             "drops": [5.0], "label": True}]
    errors = rules.error_rows(rows, rules.gap_rule(1.0))
    assert {e["error"] for e in errors} == {"FP", "FN"}


def test_choose_threshold_respects_fpr_bound():
    rows = ([{"drops": [0.5], "label": True}] * 3
            + [{"drops": [1.5], "label": False}] * 10)
    chosen = rules.choose_threshold(rows, [0.5, 1.0, 2.0], rules.gap_rule)
    assert chosen == 1.0


def test_choose_threshold_falls_back_when_no_threshold_qualifies():
    rows = [{"drops": [0.5], "label": False}] * 10
    chosen = rules.choose_threshold(rows, [1.0, 2.0], rules.gap_rule,
                                    fpr_bound=0.0)
    assert chosen == 2.0