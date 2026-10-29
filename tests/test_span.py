"""Span-level stage 2 allows an empty span and ignores high-drop tokens."""
from guard import stage2


def test_span_keeps_only_low_drop_tokens():
    drops = [2.0, 0.2, 0.4, 3.0]
    assert stage2.span_indices(drops, 0.5) == [1, 2]
    summary = stage2.span_summary([-0.1, -8.0, -7.0, -0.2], [1, 2])
    assert summary["empty"] is False
    assert summary["length"] == 2
    assert summary["minimum"] == -8.0
    assert summary["mean"] == -7.5


def test_empty_span_allows():
    summary = stage2.span_summary([-1.0, -2.0], [])
    assert summary["empty"] is True
    assert stage2.flag_span(summary, threshold=-0.1) is False


def test_span_blocks_only_below_the_threshold():
    summary = stage2.span_summary([-4.0], [0])
    assert stage2.flag_span(summary, threshold=-3.0) is True
    assert stage2.flag_span(summary, threshold=-5.0) is False


def test_stage2_alone_scores_every_row():
    from experiments.span_stage2 import _escalation
    rows = [{"stage1_flag": False}, {"stage1_flag": True}]
    assert _escalation(rows, False)["passes"] == 2
    assert _escalation(rows, True)["passes"] == 1


def test_missing_fence_uses_the_fixed_prefix():
    prefix, source = stage2.fence_context("")
    assert source == "fixed_prefix"
    assert prefix
